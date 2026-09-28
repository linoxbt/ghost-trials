"""Create private organization access tokens; never overwrite or print secrets."""
import argparse
import json
import os
from pathlib import Path
import secrets

from .execution_setup import private_create


def prepare_access(directory):
    if directory.is_symlink():
        raise ValueError("Refusing symlinked credential directory")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / "access.env"
    if path.is_symlink():
        raise ValueError("Refusing symlinked credential file")
    if not path.exists():
        private_create(path, "".join(f"GHOST_{role.upper()}_TOKEN={secrets.token_urlsafe(48)}\n"
                                    for role in ("admin", "operator", "viewer")))
    os.chmod(path, 0o600)
    return {"access_file": str(path), "secrets_printed": False, "existing_credentials_preserved": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("deployment/private"))
    args = parser.parse_args()
    print(json.dumps(prepare_access(args.directory)))


if __name__ == "__main__":
    main()
