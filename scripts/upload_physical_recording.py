"""Upload a completed hardware recording without starting robot motion or judging.

Set GHOST_BACKEND_URL and GHOST_RECORDING_UPLOAD_TOKEN privately. This token is
an existing operator credential, never a new bypass around individual accounts.
Individual-account users should use the authenticated dashboard uploader.
"""
import argparse
import json
import os
from pathlib import Path

import httpx

from ghost_trials.physical import FILES, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    base = os.environ["GHOST_BACKEND_URL"].rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("A trusted HTTPS backend is required")
    headers = {"Authorization": "Bearer " + os.environ["GHOST_RECORDING_UPLOAD_TOKEN"]}
    manifest = {name: {"sha256": file_digest(args.bundle/name), "bytes": (args.bundle/name).stat().st_size} for name in FILES}
    with httpx.Client(base_url=base, headers=headers, timeout=120, follow_redirects=False) as client:
        route = "/physical/sessions/" + args.session_id
        response = client.put(route + "/manifest", json=manifest)
        response.raise_for_status()
        session = response.json()
        for name in sorted(FILES):
            offset = session["uploads"].get(name, {}).get("received_bytes", 0)
            total = manifest[name]["bytes"]
            with (args.bundle/name).open("rb") as stream:
                stream.seek(offset)
                while offset < total:
                    chunk = stream.read(min(262144, total-offset))
                    response = client.put(route + "/artifacts/" + name, content=chunk,
                        headers={"Content-Range": f"bytes {offset}-{offset+len(chunk)-1}/{total}",
                                 "Content-Type": "application/octet-stream"})
                    response.raise_for_status()
                    offset = response.json()["received_bytes"]
                    stream.seek(offset)
        response = client.post(route + "/validate")
        response.raise_for_status()
        print(json.dumps({"session_id": args.session_id, "status": response.json()["status"],
                          "trial_id": response.json()["trial_id"], "robot_motion_requested": False}))


if __name__ == "__main__":
    main()
