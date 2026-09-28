"""Server-owned identities, organization membership and revocable opaque sessions.

Privy verifies identities; clients never assign themselves roles or organizations.
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
        self.login_configuration = {"methods": [], "verified": False}
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
                (("email", "email_auth"), ("google", "google_oauth")) if config.get(field) is True], "verified": True}
        except (httpx.HTTPError, ValueError):
            self.login_configuration = {"methods": [], "verified": False}
        return self.login_configuration

    async def verification_key(self, token):
        if self.settings.privy_verification_key:
            return self.settings.privy_verification_key.replace("\\n", "\n")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "ES256" or not isinstance(header.get("kid"), str):
                raise ValueError()
            if self.jwks_until < time.time():
                # Fixed issuer URL, never a URL supplied by an untrusted JWT.
                app_id = self.settings.privy_app_id
                if not app_id or not app_id.isalnum():
                    raise ValueError()
                async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    response = await client.get(f"https://auth.privy.io/api/v1/apps/{app_id}/jwks.json")
                    response.raise_for_status()
                    self.jwks = response.json()["keys"]
                    self.jwks_until = time.time() + 300
            for key in self.jwks or []:
                if key.get("kid") == header["kid"] and key.get("alg") == "ES256" and key.get("crv") == "P-256":
                    return jwt.PyJWK.from_dict(key, algorithm="ES256").key
            raise ValueError()
        except (ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise HTTPException(401, "Unknown Privy signing key")
        except httpx.HTTPError:
            raise HTTPException(503, "Identity provider verification temporarily unavailable")

    def schema(self, db):
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users(subject TEXT PRIMARY KEY,display_name TEXT NOT NULL,created REAL NOT NULL,disabled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS members(organization_id TEXT,subject TEXT,role TEXT NOT NULL,PRIMARY KEY(organization_id,subject));
            CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,subject TEXT NOT NULL,organization_id TEXT NOT NULL,expires REAL NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS invites(digest TEXT PRIMARY KEY,organization_id TEXT NOT NULL,role TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY,limit_cents INTEGER NOT NULL,used_cents INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS account_audit(sequence INTEGER PRIMARY KEY AUTOINCREMENT,at REAL,organization_id TEXT,subject TEXT,role TEXT,action TEXT,target TEXT);
        """)

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

    def start_session(self, claims):
        subject = claims["sub"]
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
        principal = Principal(subject, membership["organization_id"], membership["role"])
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
            return Principal(row["subject"], row["organization_id"], row["role"]) if row else None

    def revoke(self, raw):
        with self.store.connect() as db:
            self.schema(db)
            db.execute("DELETE FROM sessions WHERE digest=?", (hashlib.sha256(raw.encode()).hexdigest(),))

    def profile(self, principal):
        if principal.kind != "privy":
            return {"subject": principal.subject, "display_name": "Private team" if principal.kind == "role_token" else "Demo visitor", "organizations": []}
        with self.store.connect() as db:
            self.schema(db)
            user = dict(db.execute("SELECT subject,display_name,created FROM users WHERE subject=?", (principal.subject,)).fetchone())
            user["organizations"] = [dict(row) for row in db.execute("SELECT o.id,o.name,m.role FROM organizations o JOIN members m ON o.id=m.organization_id WHERE m.subject=?", (principal.subject,))]
            return user

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
            if not db.execute("SELECT 1 FROM members WHERE subject=? AND organization_id=?", (subject, principal.organization_id)).fetchone():
                raise HTTPException(404, "Member not found")
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
