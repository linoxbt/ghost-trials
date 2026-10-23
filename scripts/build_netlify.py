"""Build the Netlify frontend and proxy rules for an external FastAPI backend."""

import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ghost_trials.csp import PAGE_CSP  # noqa: E402  (dependency-free module shared with the backend)

SOURCE = ROOT / "static"
TARGET = ROOT / "netlify-dist"
ORIGIN = os.environ.get("GHOST_BACKEND_ORIGIN", "").rstrip("/")
PAGE_HEADERS = f"""  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: {PAGE_CSP}
"""
# Static files only: proxied backend routes keep their own headers (the /artifacts preview must stay
# frameable by the workspace). /assets/* covers the raw HTML copies served there too.
HEADERS = "".join(f"{path}\n{PAGE_HEADERS}" for path in ("/", "/index.html", "/app/*", "/docs/*", "/assets/*")) + """/assets/auth/chunks/*
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
             "openapi.json", "api/docs", "api/redoc", "ready", "account", "organizations", "agent-targets",
             "csp-report")
    wildcards = ("trials/*", "hunts/*", "ghost-cases/*", "agent-trials/*", "artifacts/*", "generated/*", "auth/*", "organizations/*", "physical/*")
    # Operator /ops routes are reached on the backend origin directly, not through the public site.
    rules = [f"/{path} {ORIGIN}/{path} 200!" for path in exact]
    rules.extend(f"/{path} {ORIGIN}/{path.replace('*', ':splat')} 200!" for path in wildcards)
    (TARGET / "_redirects").write_text("\n".join(rules) + "\n")
    (TARGET / "_headers").write_text(HEADERS)
    print(f"Built Netlify frontend and {len(rules)} backend routes")


if __name__ == "__main__":
    main()
