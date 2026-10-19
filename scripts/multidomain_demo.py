"""Execute measured MuJoCo and bundled-agent Hunts with no paid services.

    uv run python -m scripts.multidomain_demo --output data/multidomain-demo
"""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from .cpu_smoke import run as run_cpu


async def run(root: Path) -> dict:
    # run_cpu sets explicit CPU/no-provider environment before importing the app.
    physical = await run_cpu(root, trials=9, strategy="grid")
    from ghost_trials.app import app, lifespan
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://demo") as client:
            created = await client.post("/hunts", json={"domain": "ai_agent",
                "target_id": "reference-vulnerable-v1",
                "objective": {"verification_objective": "tool_output_manipulation"},
                "max_trials": 6, "strategy": "adaptive"})
            created.raise_for_status()
            hunt_id = created.json()["hunt_id"]
            for _ in range(100):
                hunt = (await client.get(f"/hunts/{hunt_id}")).json()
                if hunt["status"] in {"complete", "blocked"}:
                    break
                await asyncio.sleep(.1)
            if hunt["status"] != "complete" or not hunt["case_ids"]:
                raise RuntimeError(f"Agent Hunt did not discover a verified failure: {hunt}")
            case = (await client.get(f"/ghost-cases/{hunt['case_ids'][0]}")).json()
            baseline = (await client.get(f"/agent-trials/{case['baseline_trial_id']}")).json()
            if not baseline["evidence_verified"] or baseline["status"] != "verified_failure":
                raise RuntimeError("Agent failure evidence did not verify")
            replay = await client.post(f"/agent-trials/{case['baseline_trial_id']}/replay")
            replay.raise_for_status()
            if not replay.json()["same_verdict"] or not replay.json()["evidence_verified"]:
                raise RuntimeError("Agent failure did not reproduce")
            regression = await client.post(f"/ghost-cases/{case['case_id']}/regressions",
                                           json={"target_id": "reference-corrected-v2"})
            regression.raise_for_status()
            if regression.json()["outcome"] != "fixed_on_case":
                raise RuntimeError("Corrected reference agent did not pass saved case")
            agent = {"hunt_id": hunt_id, "trials": len(hunt["candidates"]),
                     "case_id": case["case_id"], "failed_assertions": case["assertion_ids"],
                     "forbidden_event": next(e for e in baseline["tool_events"] if not e["authorized"]),
                     "evidence_verified": baseline["evidence_verified"],
                     "reproduction_status": case["reproduction_status"],
                     "regression_outcome": regression.json()["outcome"]}
            return {"physical_ai": physical, "ai_agent": agent,
                    "scope": "CPU MuJoCo physics plus controlled bundled reference agent; no hardware or arbitrary customer code"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        print(json.dumps(asyncio.run(run(args.output.resolve())), indent=2))
    else:
        with tempfile.TemporaryDirectory(prefix="ghost-multidomain-") as directory:
            print(json.dumps(asyncio.run(run(Path(directory))), indent=2))


if __name__ == "__main__":
    main()
