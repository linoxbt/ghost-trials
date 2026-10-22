"""Build the Netlify frontend and proxy rules for an external FastAPI backend."""

import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static"
TARGET = ROOT / "netlify-dist"
ORIGIN = os.environ.get("GHOST_BACKEND_ORIGIN", "").rstrip("/")
# Enforced: no framing, no plugins, no base-tag hijacking. The full policy is report-only until the
# Privy sign-in flow has been exercised under it, so a missed origin cannot break login.
CSP_ENFORCED = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
CSP_REPORT_ONLY = ("default-src 'self'; script-src 'self' https://challenges.cloudflare.com; "
                   "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
                   "connect-src 'self' https://auth.privy.io wss://relay.walletconnect.com wss://relay.walletconnect.org "
                   "https://*.rpc.privy.systems https://explorer-api.walletconnect.com; "
                   "frame-src https://auth.privy.io https://verify.walletconnect.com https://verify.walletconnect.org "
                   "https://challenges.cloudflare.com; worker-src 'self' blob:; media-src 'self' blob:")
PAGE_HEADERS = f"""  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: {CSP_ENFORCED}
  Content-Security-Policy-Report-Only: {CSP_REPORT_ONLY}
"""
# Static pages only: proxied backend routes keep their own headers (the /artifacts preview must stay
# frameable by the workspace).
HEADERS = "".join(f"{path}\n{PAGE_HEADERS}" for path in ("/", "/index.html", "/app/*", "/docs/*")) + """/assets/*
  X-Content-Type-Options: nosniff
/assets/auth/chunks/*
  Cache-Control: public, max-age=31536000, immutable
"""


def main() -> None:
    parsed = urlsplit(ORIGIN)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise SystemExit("GHOST_BACKEND_ORIGIN must be a public HTTPS origin without a path or credentials")
    if TARGET.is_symlink():
        raise SystemExit("Refusing to build through a symlinked output directory")
    # Start clean so superseded hashed bundles are never republished.
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir()
    shutil.copytree(SOURCE, TARGET / "assets", dirs_exist_ok=True)
    (TARGET / "index.html").write_bytes((SOURCE / "landing.html").read_bytes())
    (TARGET / "app").mkdir(exist_ok=True)
    workspace = (SOURCE / "index.html").read_text()
    workspace = workspace.replace("<head>", '<head>\n  <meta name="ghost-transport" content="poll">', 1)
    (TARGET / "app" / "index.html").write_text(workspace)
    (TARGET / "docs").mkdir(exist_ok=True)
    (TARGET / "docs" / "index.html").write_bytes((SOURCE / "docs.html").read_bytes())
    (TARGET / "docs" / "agent").mkdir(exist_ok=True)
    (TARGET / "docs" / "agent" / "index.html").write_bytes((SOURCE / "agent-guide.html").read_bytes())

    exact = ("health", "capabilities", "scenarios", "trials", "agent-trials", "hunts", "ghost-cases",
             "failure-families", "safety-score", "benchmarks", "comparisons", "demonstration-readiness",
             "openapi.json", "api/docs", "api/redoc", "ready", "account", "organizations", "agent-targets")
    wildcards = ("trials/*", "hunts/*", "ghost-cases/*", "agent-trials/*", "artifacts/*", "generated/*", "auth/*", "organizations/*", "physical/*")
    # Operator /ops routes are reached on the backend origin directly, not through the public site.
    rules = [f"/{path} {ORIGIN}/{path} 200!" for path in exact]
    rules.extend(f"/{path} {ORIGIN}/{path.replace('*', ':splat')} 200!" for path in wildcards)
    (TARGET / "_redirects").write_text("\n".join(rules) + "\n")
    (TARGET / "_headers").write_text(HEADERS)
    print(f"Built Netlify frontend and {len(rules)} backend routes")


if __name__ == "__main__":
    main()
