"""Server-owned identities, organization membership and revocable opaque sessions.

Identity providers verify users; clients never assign themselves roles or organizations.
Application budgets bound admission, not external provider charges or idle VMs.
"""
import hashlib
import secrets
import time
import uuid
import httpx
from dataclasses import dataclass

import jwt
from fastapi import HTTPException


@dataclass(frozen=True)
class Principal:
    subject: str
    organization_id: str
    role: str
    kind: str = "privy"


def reserve_budget(db, trial_id, org_id, cents, platform_limit):
    # Called within the same immediate transaction as queue acceptance.
    db.execute("CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY,limit_cents INTEGER NOT NULL,used_cents INTEGER NOT NULL DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS reservations(trial_id TEXT PRIMARY KEY,organization_id TEXT,cents INTEGER NOT NULL)")
    db.execute("INSERT INTO budgets(id,limit_cents,used_cents) VALUES('platform',?,0) ON CONFLICT(id) DO UPDATE SET limit_cents=excluded.limit_cents", (platform_limit,))
    for account in ("platform", org_id):
        row = db.execute("SELECT * FROM budgets WHERE id=?", (account,)).fetchone()
        if not row or row["used_cents"] + cents > row["limit_cents"]:
            raise HTTPException(402, "Execution admission budget exhausted; an operator must allocate budget")
    for account in ("platform", org_id):
        db.execute("UPDATE budgets SET used_cents=used_cents+? WHERE id=?", (cents, account))
    db.execute("INSERT INTO reservations VALUES(?,?,?)", (trial_id, org_id, cents))
    # No automatic refunds: even a failed request may have incurred external cost.


class Accounts:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.jwks = None
        self.jwks_until = 0
        self.jwks_fetched_at = 0
        self.dynamic_jwks = None
        self.dynamic_jwks_until = 0
        self.dynamic_jwks_fetched_at = 0
        self.login_configuration = {"methods": [], "passkey_signup_enabled": False, "verified": False}
        self.login_configuration_until = 0

    async def login_methods(self):
        if self.login_configuration_until > time.time():
            return self.login_configuration
        self.login_configuration_until = time.time() + 60
        try:
            app_id = self.settings.privy_app_id
            if not app_id or not app_id.isalnum():
                return self.login_configuration
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(f"https://auth.privy.io/api/v1/apps/{app_id}", headers={"privy-app-id":app_id})
                response.raise_for_status()
                config = response.json()
            self.login_configuration = {"methods": [name for name, field in
                (("email", "email_auth"), ("google", "google_oauth"), ("passkey", "passkey_auth"))
                if config.get(field) is True],
                "passkey_signup_enabled": config.get("passkey_auth") is True and
                    config.get("passkeys_for_signup_enabled") is True,
                "verified": True}
        except (httpx.HTTPError, ValueError):
            self.login_configuration = {"methods": [], "passkey_signup_enabled": False, "verified": False}
        return self.login_configuration

    async def verification_key(self, token):
        if self.settings.privy_verification_key:
            return self.settings.privy_verification_key.replace("\\n", "\n")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "ES256" or not isinstance(header.get("kid"), str):
                raise ValueError()
            known = any(key.get("kid") == header["kid"] for key in self.jwks or [])
            # Refetch on expiry, or on an unseen key ID (provider rotation) at most every 30 seconds.
            if self.jwks_until < time.time() or (not known and self.jwks_fetched_at + 30 < time.time()):
                # Fixed issuer URL, never a URL supplied by an untrusted JWT.
                app_id = self.settings.privy_app_id
                if not app_id or not app_id.isalnum():
                    raise ValueError()
                async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    response = await client.get(f"https://auth.privy.io/api/v1/apps/{app_id}/jwks.json")
                    response.raise_for_status()
                    keys = response.json()["keys"]
                    if not isinstance(keys, list) or len(keys) > 20:
                        raise ValueError("Unexpected Privy JWKS shape")
                    self.jwks = keys
                    self.jwks_until = time.time() + 300
                    self.jwks_fetched_at = time.time()
            for key in self.jwks or []:
                if key.get("kid") == header["kid"] and key.get("alg") == "ES256" and key.get("crv") == "P-256":
                    return jwt.PyJWK.from_dict(key, algorithm="ES256").key
            raise ValueError()
        except (ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise HTTPException(401, "Unknown Privy signing key")
        except httpx.HTTPError:
            raise HTTPException(503, "Identity provider verification temporarily unavailable")

    async def dynamic_verification_key(self, token):
        environment_id = self.settings.dynamic_environment_id
        try:
            uuid.UUID(environment_id or "")
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError()
            known = any(key.get("kid") == header["kid"] for key in self.dynamic_jwks or [])
            if self.dynamic_jwks_until < time.time() or (not known and self.dynamic_jwks_fetched_at + 30 < time.time()):
                # Fixed provider URL; neither the token nor request controls the key source.
                url = f"https://app.dynamic.xyz/api/v0/sdk/{environment_id}/.well-known/jwks"
                async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    keys = response.json()["keys"]
                if not isinstance(keys, list) or len(keys) > 20:
                    raise ValueError()
                self.dynamic_jwks = keys
                self.dynamic_jwks_until = time.time() + 300
                self.dynamic_jwks_fetched_at = time.time()
            for key in self.dynamic_jwks or []:
                if key.get("kid") == header["kid"] and key.get("kty") == "RSA" and key.get("alg") in (None, "RS256"):
                    return jwt.PyJWK.from_dict(key, algorithm="RS256").key
            raise ValueError()
        except (ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise HTTPException(401, "Unknown Dynamic signing key")
        except httpx.HTTPError:
            raise HTTPException(503, "Identity provider verification temporarily unavailable")

    def schema(self, db):
        # Create account tables once per database file, not on every authenticated request.
        path = getattr(self.store, "database_path", None)
        if path is not None and getattr(self, "_schema_path", None) == path:
            return
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users(subject TEXT PRIMARY KEY,display_name TEXT NOT NULL,created REAL NOT NULL,disabled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS members(organization_id TEXT,subject TEXT,role TEXT NOT NULL,PRIMARY KEY(organization_id,subject));
            CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,subject TEXT NOT NULL,organization_id TEXT NOT NULL,expires REAL NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS invites(digest TEXT PRIMARY KEY,organization_id TEXT NOT NULL,role TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY,limit_cents INTEGER NOT NULL,used_cents INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS account_audit(sequence INTEGER PRIMARY KEY AUTOINCREMENT,at REAL,organization_id TEXT,subject TEXT,role TEXT,action TEXT,target TEXT);
        """)
        self._schema_path = path

    def verify(self, token, key=None):
        if not self.settings.privy_app_id or not (key or self.settings.privy_verification_key):
            raise HTTPException(503, "Privy verification is not configured")
        try:
            claims = jwt.decode(token, key or self.settings.privy_verification_key.replace("\\n", "\n"), algorithms=["ES256"],
                audience=self.settings.privy_app_id, issuer="privy.io",
                options={"require": ["sub", "iss", "aud", "iat", "exp", "sid"]})
            if not isinstance(claims["sub"], str) or not claims["sub"].startswith("did:privy:") or len(claims["sub"]) > 200:
                raise ValueError("Invalid subject")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError):
            raise HTTPException(401, "Invalid or expired Privy access token")

    def verify_dynamic(self, token, key):
        environment_id = self.settings.dynamic_environment_id
        audience = self.settings.dynamic_jwt_audience
        if not environment_id or not audience or key is None:
            raise HTTPException(503, "Dynamic verification is not configured")
        try:
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience,
                issuer=f"app.dynamic.xyz/{environment_id}",
                options={"require": ["sub", "iss", "aud", "iat", "exp", "environment_id"]})
            if claims["environment_id"] != environment_id:
                raise ValueError("Wrong Dynamic environment")
            subject = claims["sub"]
            if not isinstance(subject, str) or str(uuid.UUID(subject)) != subject:
                raise ValueError("Invalid Dynamic subject")
            if "requiresAdditionalAuth" in claims.get("scopes", []):
                raise ValueError("Additional authentication required")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError):
            raise HTTPException(401, "Invalid or expired Dynamic access token")

    def start_session(self, claims, provider="privy"):
        subject = f"dynamic:{claims['sub']}" if provider == "dynamic" else claims["sub"]
        raw = "usr_" + secrets.token_urlsafe(48)
        expires = min(float(claims["exp"]), time.time() + self.settings.ghost_privy_session_seconds)
        with self.store.connect() as db:
            self.schema(db)
            db.execute("BEGIN IMMEDIATE")
            user = db.execute("SELECT * FROM users WHERE subject=?", (subject,)).fetchone()
            if not user:
                if not self.settings.ghost_public_signup_enabled:
                    raise HTTPException(403, "Public account creation is disabled")
                org_id = "org_" + uuid.uuid4().hex
                db.execute("INSERT INTO users(subject,display_name,created) VALUES(?,?,?)", (subject, "New member", time.time()))
                db.execute("INSERT INTO organizations VALUES(?,?,?,?)", (org_id, "My evaluation lab", subject, time.time()))
                db.execute("INSERT INTO members VALUES(?,?,'admin')", (org_id, subject))
            elif user["disabled"]:
                raise HTTPException(403, "Account disabled")
            membership = db.execute("SELECT * FROM members WHERE subject=? ORDER BY organization_id LIMIT 1", (subject,)).fetchone()
            if not membership:
                raise HTTPException(403, "Account has no workspace membership")
            db.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (hashlib.sha256(raw.encode()).hexdigest(), subject,
                       membership["organization_id"], expires, time.time()))
        principal = Principal(subject, membership["organization_id"], membership["role"], provider)
        self.audit(principal, "account_login")
        return raw, principal, expires

    def resolve(self, raw):
        if not raw.startswith("usr_") or len(raw) > 200:
            return None
        with self.store.connect() as db:
            self.schema(db)
            row = db.execute("SELECT s.subject,s.organization_id,m.role FROM sessions s JOIN users u ON u.subject=s.subject "
                "JOIN members m ON m.subject=s.subject AND m.organization_id=s.organization_id "
                "WHERE s.digest=? AND s.expires>? AND u.disabled=0", (hashlib.sha256(raw.encode()).hexdigest(), time.time())).fetchone()
            if not row:
                return None
            kind = "dynamic" if row["subject"].startswith("dynamic:") else "privy"
            if kind != self.settings.ghost_auth_provider:
                return None
            return Principal(row["subject"], row["organization_id"], row["role"], kind)

    def revoke(self, raw):
        with self.store.connect() as db:
            self.schema(db)
            db.execute("DELETE FROM sessions WHERE digest=?", (hashlib.sha256(raw.encode()).hexdigest(),))

    def profile(self, principal):
        if principal.kind not in {"privy", "dynamic"}:
            return {"subject": principal.subject, "display_name": "Private team" if principal.kind == "role_token" else "Demo visitor", "organizations": []}
        with self.store.connect() as db:
            self.schema(db)
            user = dict(db.execute("SELECT subject,display_name,created FROM users WHERE subject=?", (principal.subject,)).fetchone())
            user["organizations"] = [dict(row) for row in db.execute("SELECT o.id,o.name,m.role FROM organizations o JOIN members m ON o.id=m.organization_id WHERE m.subject=?", (principal.subject,))]
            return user

    def update_display_name(self, principal, display_name):
        if principal.kind not in {"privy", "dynamic"}:
            raise HTTPException(401, "Individual sign-in required")
        name = display_name.strip()
        if not 2 <= len(name) <= 80 or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise HTTPException(422, "Display name must be 2–80 characters on one line")
        with self.store.connect() as db:
            self.schema(db)
            if not db.execute("UPDATE users SET display_name=? WHERE subject=? AND disabled=0",
                              (name, principal.subject)).rowcount:
                raise HTTPException(404, "Account not found")
        self.audit(principal, "profile_updated")
        return self.profile(principal)

    def switch(self, raw, org_id):
        principal = self.resolve(raw)
        if not principal:
            raise HTTPException(401, "Sign in required")
        with self.store.connect() as db:
            if not db.execute("SELECT 1 FROM members WHERE subject=? AND organization_id=?", (principal.subject, org_id)).fetchone():
                raise HTTPException(404, "Workspace not found")
            db.execute("UPDATE sessions SET organization_id=? WHERE digest=?", (org_id, hashlib.sha256(raw.encode()).hexdigest()))
        current = self.resolve(raw)
        self.audit(current, "workspace_switch", org_id)

    def create_organization(self, principal, name):
        if not 2 <= len(name.strip()) <= 80:
            raise HTTPException(422, "Workspace name must contain 2–80 non-whitespace characters")
        org_id = "org_" + uuid.uuid4().hex
        with self.store.connect() as db:
            self.schema(db)
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM organizations WHERE owner=?", (principal.subject,)).fetchone()[0] >= 5:
                raise HTTPException(409, "Maximum of five owned workspaces reached")
            db.execute("INSERT INTO organizations VALUES(?,?,?,?)", (org_id, name, principal.subject, time.time()))
            db.execute("INSERT INTO members VALUES(?,?,'admin')", (org_id, principal.subject))
        self.audit(Principal(principal.subject, org_id, "admin"), "workspace_created", org_id)
        return org_id

    def organization(self, principal):
        with self.store.connect() as db:
            self.schema(db)
            row = db.execute("SELECT * FROM organizations WHERE id=?", (principal.organization_id,)).fetchone()
            if not row:
                return {"id": principal.organization_id, "name": "Private team" if principal.kind == "role_token" else "Synthetic demo", "members": [], "budget": self.budget(principal.organization_id)}
            result = dict(row)
            result["members"] = [dict(item) for item in db.execute("SELECT m.subject,m.role,u.display_name FROM members m JOIN users u ON m.subject=u.subject WHERE m.organization_id=?", (principal.organization_id,))]
        result["budget"] = self.budget(principal.organization_id)
        return result

    def invite(self, principal, role):
        raw = secrets.token_urlsafe(32)
        with self.store.connect() as db:
            self.schema(db)
            db.execute("INSERT INTO invites VALUES(?,?,?,?,0)", (hashlib.sha256(raw.encode()).hexdigest(), principal.organization_id, role, time.time() + 86400))
        self.audit(principal, "member_invited")
        return raw

    def accept_invite(self, principal, raw):
        with self.store.connect() as db:
            self.schema(db)
            db.execute("BEGIN IMMEDIATE")
            invite = db.execute("SELECT * FROM invites WHERE digest=? AND expires>? AND used=0", (hashlib.sha256(raw.encode()).hexdigest(), time.time())).fetchone()
            if not invite:
                raise HTTPException(404, "Invitation expired or already used")
            # Never downgrade/promote an existing membership via invitation replay.
            db.execute("INSERT INTO members VALUES(?,?,?) ON CONFLICT(organization_id,subject) DO NOTHING", (invite["organization_id"], principal.subject, invite["role"]))
            db.execute("UPDATE invites SET used=1 WHERE digest=?", (invite["digest"],))
        with self.store.connect() as db:
            role = db.execute("SELECT role FROM members WHERE subject=? AND organization_id=?",
                (principal.subject, invite["organization_id"])).fetchone()[0]
        self.audit(Principal(principal.subject, invite["organization_id"], role), "invitation_accepted")
        return invite["organization_id"]

    def member_change(self, principal, subject, role=None):
        with self.store.connect() as db:
            self.schema(db)
            owner = db.execute("SELECT owner FROM organizations WHERE id=?", (principal.organization_id,)).fetchone()
            if owner and subject == owner[0]:
                raise HTTPException(409, "The workspace owner cannot be removed or demoted")
            member = db.execute("SELECT role FROM members WHERE subject=? AND organization_id=?", (subject, principal.organization_id)).fetchone()
            if not member:
                raise HTTPException(404, "Member not found")
            # Admins cannot take over a workspace from each other: only the owner changes admin seats
            # (an admin may still step down or leave on their own).
            if ((member[0] == "admin" or role == "admin") and subject != principal.subject
                    and not (owner and principal.subject == owner[0])):
                raise HTTPException(403, "Only the workspace owner can change administrators")
            if role:
                db.execute("UPDATE members SET role=? WHERE subject=? AND organization_id=?", (role, subject, principal.organization_id))
            else:
                db.execute("DELETE FROM members WHERE subject=? AND organization_id=?", (subject, principal.organization_id))
                db.execute("DELETE FROM sessions WHERE subject=? AND organization_id=?", (subject, principal.organization_id))
        self.audit(principal, "member_role_changed" if role else "member_removed", subject)

    def budget(self, org_id):
        with self.store.connect() as db:
            self.schema(db)
            row = db.execute("SELECT limit_cents,used_cents FROM budgets WHERE id=?", (org_id,)).fetchone()
            return dict(row) if row else {"limit_cents": 0, "used_cents": 0}

    def allocate_budget(self, org_id, limit):
        with self.store.connect() as db:
            self.schema(db)
            db.execute("BEGIN IMMEDIATE")
            if org_id != "legacy" and not db.execute("SELECT 1 FROM organizations WHERE id=?", (org_id,)).fetchone():
                raise HTTPException(404, "Workspace not found")
            used = db.execute("SELECT used_cents FROM budgets WHERE id=?", (org_id,)).fetchone()
            if used and limit < used[0]:
                raise HTTPException(409, "Budget cannot be reduced below existing reservations")
            db.execute("INSERT INTO budgets(id,limit_cents) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET limit_cents=excluded.limit_cents", (org_id, limit))

    def audit(self, principal, action, target=None):
        self.store.audit(action, principal.role, target, organization_id=principal.organization_id, subject=principal.subject)

    def audit_records(self, principal):
        with self.store.connect() as db:
            self.schema(db)
            return [dict(row) for row in db.execute("SELECT at,subject,role,action,target FROM account_audit WHERE organization_id=? ORDER BY sequence DESC LIMIT 100", (principal.organization_id,))]
