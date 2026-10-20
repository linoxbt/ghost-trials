"""Generate a public, non-customer reference run from actual CPU physics.

The exported reference is excluded from every workspace's trial list and score.
Run this script only when intentionally refreshing the checked-in example.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import shutil
import tempfile

from ghost_trials.cpu_evidence import verify_cpu_bundle
from scripts.cpu_live_review import run


ARTIFACTS = ("recipe.json", "summary.json", "telemetry.jsonl", "trajectory.svg",
             "manifest.json", "verification.json", "scenario.json")


async def export(target: Path, *, replace: bool = False) -> dict:
    if target.exists() and any(target.iterdir()) and not replace:
        raise ValueError("Reference target must be new and empty; remove old assets only after explicit review")
    if replace and target.exists() and (target.is_symlink() or
            any(path.is_symlink() or path.name not in {*ARTIFACTS, "index.json"} for path in target.iterdir())):
        raise ValueError("Reference target contains unexpected files or symlinks")
    with tempfile.TemporaryDirectory(prefix="ghost-reference-") as directory:
        source = Path(directory)
        report = await run(source, live_nebius=False, seed=42)
        bundle = source / "artifacts" / "trials" / report["trial_id"]
        verification = verify_cpu_bundle(bundle, report["checkpoint_digest"])
        if verification["status"] != "cpu_trace_metrics_verified":
            raise RuntimeError("Reference evidence verification failed")
        target.mkdir(parents=True, exist_ok=True)
        for name in ARTIFACTS:
            shutil.copy2(bundle / name, target / name)
        index = {
            "kind": "public_reference_cpu_simulation",
            "customer_score_eligible": False,
            "scope": "Project reference controller and MuJoCo tabletop only; not G1 or hardware",
            "trial_id": report["trial_id"],
            "policy_name": report["policy_name"],
            "checkpoint_digest": report["checkpoint_digest"],
            "simulator_version": report["simulator_version"],
            "seed": report["seed"],
            "task_completed": report["task_completed"],
            "object_final_x_m": report["object_final_x_m"],
            "simulation_duration_s": report["simulation_duration_s"],
            "evidence_verification": report["evidence_verification"],
            "model_review_status": "not_requested",
            "artifact_files": list(ARTIFACTS),
            "reproduce": "uv run --extra physics python -m scripts.cpu_live_review --output /tmp/ghost-reference-replay --seed 42",
        }
        (target / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("static/reference/gantry-v1"))
    parser.add_argument("--replace", action="store_true", help="Refresh the checked-in reference after review")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(export(args.output, replace=args.replace)), indent=2))


if __name__ == "__main__":
    main()
