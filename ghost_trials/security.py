"""Role tokens and short-lived signed cookies for a private organization."""
import base64
import hashlib
import hmac
import json
import time
import re
import secrets
import uuid
import os
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.responses import JSONResponse
from .accounts import Accounts, Principal


class AccessControl:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.accounts = Accounts(store, settings)
        self.tokens = {role: token for role, token in {
            "admin": settings.ghost_admin_token, "operator": settings.ghost_operator_token,
            "viewer": settings.ghost_viewer_token}.items() if token}
        identity_configured = settings.privy_app_id if settings.ghost_auth_provider == "privy" else settings.dynamic_environment_id
        self.enabled = bool(self.tokens or identity_configured or settings.ghost_customer_auth_required)
        if self.tokens and (any(len(token) < 32 for token in self.tokens.values()) or len(set(self.tokens.values())) != len(self.tokens)):
            raise ValueError("Role tokens must be distinct and at least 32 characters")
        if settings.ghost_public_deployment or os.environ.get("RAILWAY_ENVIRONMENT_ID"):
            if not settings.ghost_customer_auth_required or not identity_configured:
                raise ValueError("Public deployment requires individual sign-in")
            if settings.ghost_auth_provider == "dynamic" and not settings.dynamic_jwt_audience:
                raise ValueError("Public Dynamic deployment requires a JWT audience")
            if not settings.ghost_cookie_secure:
                raise ValueError("Public deployment requires secure session cookies")
            origins = [item.strip() for item in settings.ghost_allowed_origins.split(",") if item.strip()]
            if not origins or any((parts := urlsplit(item)).scheme != "https" or not parts.netloc
                                  or parts.path or parts.query or parts.fragment or parts.username or parts.password
                                  for item in origins):
                raise ValueError("Public deployment requires exact HTTPS allowed origins")
            if settings.ghost_auth_provider == "dynamic":
                try:
                    if str(uuid.UUID(settings.dynamic_environment_id)) != settings.dynamic_environment_id:
                        raise ValueError()
                except (TypeError, ValueError):
                    raise ValueError("Public Dynamic deployment requires a valid environment ID") from None
                if settings.dynamic_jwt_audience not in origins:
                    raise ValueError("Public Dynamic JWT audience must match an allowed frontend origin")
        if settings.ghost_mode == "production":
            if not settings.ghost_cookie_secure:
                raise ValueError("Production requires secure session cookies")
            if not settings.ghost_admin_token and not identity_configured:
                raise ValueError("Production requires an identity provider or GHOST_ADMIN_TOKEN of at least 32 characters")
            if not settings.ghost_allowed_origins:
                raise ValueError("Production requires explicit GHOST_ALLOWED_ORIGINS")
        if settings.ghost_unauthenticated_local_dev and (
                settings.ghost_public_deployment or os.environ.get("RAILWAY_ENVIRONMENT_ID")
                or settings.ghost_mode == "production"):
            raise ValueError("Unauthenticated development mode cannot run in a public deployment")
        if not self.enabled and not settings.ghost_unauthenticated_local_dev:
            raise ValueError("Configure individual authentication or explicitly enable loopback-only development mode")

    def token_role(self, token):
        for role, expected in self.tokens.items():
            if hmac.compare_digest(token.encode(), expected.encode()):
                return role
        return None

    def session(self, role):
        payload = base64.urlsafe_b64encode(json.dumps({"role": role, "exp": int(time.time()) + self.settings.ghost_session_seconds,
            "version": hashlib.sha256(self.tokens[role].encode()).hexdigest(), "jti": secrets.token_hex(16)}).encode()).decode()
        signature = hmac.new(self.tokens.get("admin", next(iter(self.tokens.values()))).encode(), payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def cookie_role(self, cookie):
        try:
            payload, signature = cookie.split(".", 1)
            expected = hmac.new(self.tokens.get("admin", next(iter(self.tokens.values()))).encode(), payload.encode(), hashlib.sha256).hexdigest()
            data = json.loads(base64.urlsafe_b64decode(payload))
            role = data["role"]
            if hmac.compare_digest(signature, expected) and data["exp"] > time.time() and role in self.tokens:
                # Sessions without a jti predate logout revocation; they must sign in again.
                if (data["version"] == hashlib.sha256(self.tokens[role].encode()).hexdigest() and isinstance(data.get("jti"), str)
                        and not (self.store is not None and self.store.session_revoked(data["jti"]))):
                    return role
        except (ValueError, KeyError, TypeError, StopIteration):
            pass
        return None

    def revoke_role_session(self, cookie):
        """Logout for role-token sessions: remember the signed session ID until it would expire."""
        try:
            payload, signature = cookie.split(".", 1)
            expected = hmac.new(self.tokens.get("admin", next(iter(self.tokens.values()))).encode(), payload.encode(), hashlib.sha256).hexdigest()
            data = json.loads(base64.urlsafe_b64decode(payload))
            if self.store is not None and hmac.compare_digest(signature, expected) and isinstance(data.get("jti"), str):
                self.store.revoke_session(data["jti"], int(data["exp"]))
        except (ValueError, KeyError, TypeError, StopIteration):
            pass

    def role(self, connection):
        principal = getattr(connection.state, "principal", None)
        if principal:
            # Reload membership to invalidate removed members and changed roles (once per request).
            if principal.kind in {"privy", "dynamic"}:
                if not hasattr(connection.state, "resolved_role"):
                    current = self.accounts.resolve(connection.cookies.get("ghost_session", ""))
                    connection.state.resolved_role = current.role if current else None
                return connection.state.resolved_role
            return principal.role
        if not self.enabled:
            return "admin"  # Public synthetic development mode only.
        header = connection.headers.get("authorization", "")
        if header.startswith("Bearer "):
            return self.token_role(header[7:])
        return self.cookie_role(connection.cookies.get("ghost_session", ""))

    def principal(self, connection):
        raw = connection.cookies.get("ghost_session", "")
        if raw.startswith("usr_"):
            return self.accounts.resolve(raw)
        role = self.role(connection)
        if role:
            return Principal("role:" + role if self.enabled else "demo", "legacy", role,
                             "role_token" if self.enabled else "demo")
        return None

    def require_platform(self, request):
        principal = self.principal(request)
        if not principal or principal.kind in {"privy", "dynamic"}:
            raise HTTPException(403, "Platform operator credentials required")
        return self.require(request)

    def require_account(self, request, roles=("admin", "operator", "viewer")):
        principal = self.principal(request)
        if not principal or principal.kind not in {"privy", "dynamic"}:
            raise HTTPException(401, "Individual sign-in required")
        if self.role(request) not in roles:
            raise HTTPException(403, "Workspace role does not permit this action")
        return principal

    def require(self, request, roles=("admin",)):
        role = self.role(request)
        if not role:
            raise HTTPException(401, "Authentication required")
        if role not in roles:
            raise HTTPException(403, "Role does not permit this action")
        return role

    def client_ip(self, connection):
        """Client address after the configured trusted proxies, or None when it cannot be known.

        Behind a proxy with GHOST_TRUSTED_PROXY_HOPS=0 the socket peer is the proxy itself, so using it
        would put every client in one bucket; None means "apply only the platform backstop".
        """
        hops = self.settings.ghost_trusted_proxy_hops
        forwarded = [part.strip() for part in connection.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if not hops:
            return None if forwarded else (connection.client.host if connection.client else None)
        return forwarded[-hops] if len(forwarded) >= hops else (forwarded[0] if forwarded else None)

    def auth_attempt_allowed(self, request, bucket):
        """Per-client limit plus a high platform backstop, so one client cannot lock out sign-in."""
        client = self.client_ip(request)
        if client and not self.store.rate_allowed(f"{bucket}:{client}", self.settings.ghost_max_client_auth_attempts_per_minute):
            return False
        return self.store.rate_allowed(bucket, self.settings.ghost_max_auth_attempts_per_minute)

    def origin_allowed(self, request):
        allowed = {value.strip().rstrip("/") for value in self.settings.ghost_allowed_origins.split(",") if value.strip()}
        if not allowed and self.settings.ghost_mode != "production":
            allowed.add(str(request.base_url).rstrip("/"))
        return request.headers.get("origin", "").rstrip("/") in allowed

    async def middleware(self, request, call_next):
        path = request.url.path
        public = path in {"/", "/docs", "/docs/", "/docs/agent", "/health", "/auth/login", "/auth/session", "/auth/config", "/auth/privy/session", "/auth/dynamic/session", "/auth/invite"} or path.startswith("/assets/") or path.startswith("/app")
        request.state.principal = self.principal(request)
        if self.enabled and not public:
            role = self.role(request)
            if not role:
                return self.secured(JSONResponse({"detail": "Authentication required"}, 401), path, public)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                if role == "viewer" and path not in {"/account", "/auth/logout", "/organizations", "/organizations/switch", "/organizations/invitations/accept"}:
                    return self.secured(JSONResponse({"detail": "Read-only role"}, 403), path, public)
                if not request.headers.get("authorization", "").startswith("Bearer ") and not self.origin_allowed(request):
                    return self.secured(JSONResponse({"detail": "Untrusted request origin"}, 403), path, public)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            principal = request.state.principal
            physical_chunk = bool(request.method == "PUT" and self.enabled and principal and re.fullmatch(
                r"/physical/sessions/phy_[a-f0-9]{24}/artifacts/(response\.mp4|telemetry\.jsonl|capture\.json)", path))
            identity = principal.subject if principal and principal.kind in {"privy", "dynamic"} else self.role(request)
            limit = self.settings.ghost_physical_max_chunks_per_minute if physical_chunk else self.settings.ghost_max_requests_per_minute
            if identity:
                allowed = self.store.rate_allowed(("recording-upload:" if physical_chunk else "mutation:") + identity, limit)
            else:
                client = self.client_ip(request)
                allowed = ((not client or self.store.rate_allowed("mutation:anonymous:" + client, limit))
                           and self.store.rate_allowed("mutation:anonymous", self.settings.ghost_max_anonymous_requests_per_minute))
            if not allowed:
                return self.secured(JSONResponse({"detail": "Rate limit exceeded"}, 429, headers={"Retry-After": "60"}), path, public)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                # Only authenticated, role-checked physical artifact PUTs get the
                # bounded chunk allowance; ordinary JSON retains its 16 KiB cap.
                if size > (262144 if physical_chunk else 16384):
                    return self.secured(JSONResponse({"detail": "Request body too large"}, 413), path, public)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return self.secured(await call_next(request), path, public)

    def secured(self, response, path, public):
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN" if path.startswith("/artifacts/") else "DENY",
            "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(), microphone=(), geolocation=()"})
        if self.settings.ghost_cookie_secure:
            # No includeSubDomains: proxied through a custom apex domain it would pin unrelated subdomains.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if not public:
            response.headers["Cache-Control"] = "no-store"
        return response
