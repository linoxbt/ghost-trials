"""Build the Netlify frontend and proxy rules for an external FastAPI backend."""

import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static"
TARGET = ROOT / "netlify-dist"
ORIGIN = os.environ.get("GHOST_BACKEND_ORIGIN", "").rstrip("/")


def main() -> None:
    parsed = urlsplit(ORIGIN)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise SystemExit("GHOST_BACKEND_ORIGIN must be a public HTTPS origin without a path or credentials")
    if TARGET.is_symlink():
        raise SystemExit("Refusing to build through a symlinked output directory")
    TARGET.mkdir(exist_ok=True)
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
    wildcards = ("trials/*", "hunts/*", "ghost-cases/*", "agent-trials/*", "artifacts/*", "generated/*", "auth/*", "ops/*", "organizations/*", "physical/*")
    rules = [f"/{path} {ORIGIN}/{path} 200!" for path in exact]
    rules.extend(f"/{path} {ORIGIN}/{path.replace('*', ':splat')} 200!" for path in wildcards)
    (TARGET / "_redirects").write_text("\n".join(rules) + "\n")
    print(f"Built Netlify frontend and {len(rules)} backend routes")


if __name__ == "__main__":
    main()
