"""Start the existing Ghost Trials API in CPU mode without editing private .env."""
from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ.update(GHOST_MODE="cpu", GHOST_SCENARIO_PROVIDER="cpu",
                      GHOST_SIMULATOR_PROVIDER="mujoco_cpu", GHOST_JUDGE_PROVIDER="cpu",
                      GHOST_EXECUTION_BACKEND="mujoco_cpu", GHOST_POLICY_NAME="gantry-push-v1")
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Warning: bind is public/LAN-accessible; configure existing authentication and HTTPS first.")
    import uvicorn
    uvicorn.run("ghost_trials.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
