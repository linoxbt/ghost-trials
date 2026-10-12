"""Resource-bounded single CPU physics worker; invoked by CpuMujocoSimulator."""
from __future__ import annotations

import json
import resource
import sys

from .cpu_robot import execute


def main() -> None:
    # A request is a single bounded recipe, not arbitrary user code or a model file.
    resource.setrlimit(resource.RLIMIT_CPU, (18, 20))
    resource.setrlimit(resource.RLIMIT_AS, (2_500_000_000, 2_500_000_000))
    try:
        payload = json.loads(sys.stdin.buffer.read(8192))
        summary, trace, version = execute(payload["recipe"], payload["policy_id"])
        sys.stdout.write(json.dumps({"summary": summary, "trace": trace, "simulator_version": version},
                                    separators=(",", ":")))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"CPU physics worker rejected request: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
