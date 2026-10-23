"""Offline backups and bounded restore drills. Never overwrite existing data."""
import argparse
import hashlib
import json
import os
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from .config import get_settings
from .durable import DurableStore


def create_backup(store, artifact_root, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ghost-backup-") as temp:
        snapshot = Path(temp) / "state.sqlite3"
        store.backup(snapshot)
        paths = [(snapshot, "state.sqlite3")]
        if artifact_root.exists():
            for path in sorted(artifact_root.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Backups refuse symlinked evidence")
                if path.is_file():
                    paths.append((path, "artifacts/" + str(path.relative_to(artifact_root))))
        # Open exclusively; failed backups are removed only at their exact new path.
        with destination.open("xb") as output:
            os.chmod(destination, 0o600)
            with tarfile.open(fileobj=output, mode="w:gz") as archive:
                for path, name in paths:
                    archive.add(path, arcname=name, recursive=False)
        with destination.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return {"backup": str(destination), "sha256": digest, "files": len(paths),
                "requires_quiesced_jobs": True}


def restore_backup(backup, destination, expected_digest, max_bytes=10_000_000_000):
    with backup.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected_digest:
            raise ValueError("Backup digest mismatch")
    if destination.exists():
        raise ValueError("Restore destination must not exist")
    with tarfile.open(backup, "r:gz") as archive:
        members = archive.getmembers()
        total, seen = 0, set()
        for member in members:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or "\\" in member.name or member.name in seen:
                raise ValueError("Unsafe backup member")
            if member.name != "state.sqlite3" and not member.name.startswith("artifacts/"):
                raise ValueError("Unexpected backup member")
            seen.add(member.name)
            total += member.size
            if total > max_bytes or len(seen) > 100_000:
                raise ValueError("Backup exceeds restore bounds")
        if "state.sqlite3" not in seen:
            raise ValueError("Database missing from backup")
        destination.mkdir(parents=True, mode=0o700)
        for member in members:
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, path.open("xb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
            os.chmod(path, 0o600)
    # sqlite3's context manager only commits; close explicitly so the restored file is released.
    db = sqlite3.connect(f"file:{destination / 'state.sqlite3'}?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restored database integrity check failed")
    finally:
        db.close()
    return {"status": "restore_verified", "files": len(members), "destination": str(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("create")
    save.add_argument("destination", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("destination", type=Path)
    restore.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "create":
        settings = get_settings()
        store = DurableStore(settings.ghost_data_path)
        if not store.maintenance():
            parser.error("Pause submissions through POST /ops/maintenance before creating a consistent evidence backup")
        if store.job_counts()["pending"]:
            parser.error("Pause submissions and finish/cancel pending jobs before a consistent evidence backup")
        print(json.dumps(create_backup(store, settings.ghost_artifact_root, args.destination)))
    else:
        print(json.dumps(restore_backup(args.backup, args.destination, args.sha256)))


if __name__ == "__main__":
    main()
