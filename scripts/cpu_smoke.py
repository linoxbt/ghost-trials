"""Run an actual headless CPU MuJoCo Hunt through the FastAPI job queue.

Examples:
  python -m scripts.cpu_smoke --output data/cpu-validation
  python -m scripts.cpu_smoke --output data/cpu-validation --trials 16
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile

import httpx


async def run(root: Path, trials: int, strategy: str = "adaptive", policy_id: str = "gantry-push-v1") -> dict:
    # Deliberately set before app import; no developer .env may switch this to GPU or fixtures.
    os.environ.update(GHOST_MODE="cpu", GHOST_SCENARIO_PROVIDER="cpu",
                      GHOST_SIMULATOR_PROVIDER="mujoco_cpu", GHOST_JUDGE_PROVIDER="cpu",
                      GHOST_POLICY_NAME="gantry-push-v1", GHOST_EXECUTION_BACKEND="mujoco_cpu",
                      GHOST_CUSTOMER_AUTH_REQUIRED="false", GHOST_UNAUTHENTICATED_LOCAL_DEV="true", GHOST_ADMIN_TOKEN="",
                      GHOST_PUBLIC_DEPLOYMENT="false",
                      GHOST_OPERATOR_TOKEN="", GHOST_VIEWER_TOKEN="", PRIVY_APP_ID="",
                      GHOST_CPU_MODEL_REVIEW_ENABLED="false", GHOST_LIVE_EXECUTION_ENABLED="false",
                      GHOST_PROVIDER_SPENDING_CONTROLS_CONFIRMED="false", NEBIUS_API_KEY="",
                      GHOST_PIPELINE_DELAY_SECONDS="0", GHOST_JOB_TIMEOUT_SECONDS="30",
                      GHOST_DATA_PATH=str(root / "state.sqlite3"),
                      GHOST_ARTIFACT_ROOT=str(root / "artifacts"))
    from ghost_trials.app import app, lifespan
    from ghost_trials.cpu_evidence import verify_cpu_bundle
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cpu-test") as client:
            health = (await client.get("/health")).json()
            capabilities = (await client.get("/capabilities")).json()
            workspace = await client.get("/app/")
            if (health["simulator_provider"] != "mujoco_cpu" or
                    not capabilities["robot_execution_enabled"] or
                    "gantry-mlp-example" not in capabilities["supported_policies"] or
                    workspace.status_code != 200 or "hunt.js" not in workspace.text):
                raise RuntimeError("CPU frontend/API capability integration failed")
            created = await client.post("/hunts", json={"objective": {
                "task": "position a block with gantry arm", "environment": "CPU MuJoCo tabletop",
                "hazard_type": "object_positioning"}, "max_trials": trials,
                "strategy": strategy, "policy_id": policy_id})
            created.raise_for_status()
            hunt_id = created.json()["hunt_id"]
            print(f"Hunt queued: {hunt_id}", flush=True)
            for _ in range(300):
                state = (await client.get(f"/hunts/{hunt_id}")).json()
                if state["status"] in {"complete", "blocked"}:
                    break
                await asyncio.sleep(.1)
            if state["status"] != "complete":
                raise RuntimeError(f"CPU Hunt did not complete: {state['status']} {state['provider_errors']}")
            print(f"Hunt complete: {state['trials_executed']} trials", flush=True)
            cases = (await client.get("/ghost-cases")).json()
            if not cases:
                raise RuntimeError("CPU Hunt found no verified failure; increase budget or inspect task range")
            case = cases[0]
            bundle = root / "artifacts" / "trials" / case["baseline_trial_id"]
            verification = verify_cpu_bundle(bundle, case["policy"]["checkpoint_digest"])
            print(f"Evidence verified: {case['case_id']}", flush=True)
            replay_ids = []
            replay_positions = []
            for _attempt in range(2):
                replay = await client.post(f"/trials/{case['baseline_trial_id']}/replay")
                replay.raise_for_status()
                replay_id = replay.json()["trial"]["trial_id"]
                for _ in range(100):
                    repeated = (await client.get(f"/trials/{replay_id}")).json()
                    if repeated["status"] in {"done", "error", "blocked"}:
                        break
                    await asyncio.sleep(.1)
                if repeated["status"] != "done" or repeated["metrics"]["task_completed"]:
                    raise RuntimeError("Exact failure replay did not reproduce")
                replay_ids.append(replay_id)
                replay_positions.append(repeated["metrics"]["robot_metrics"]["object_final_x_m"])
            case = (await client.get(f"/ghost-cases/{case['case_id']}")).json()
            if (not set(replay_ids) <= set(case["reproduction"]["attempts"])
                    or case["reproduction"]["status"] != "reproducible"
                    or len(set(replay_positions)) != 1):
                raise RuntimeError("Repeated physical failure was not reproducible from saved evidence")
            print(f"Failure reproduced twice: {', '.join(replay_ids)}", flush=True)
            regression = await client.post(f"/ghost-cases/{case['case_id']}/regressions",
                                           json={"policy_id": "gantry-push-v2"})
            regression.raise_for_status()
            regression_id = regression.json()["candidate_trial_id"]
            print(f"Regression queued: {regression_id}", flush=True)
            for _ in range(100):
                compared = (await client.get(f"/ghost-cases/{case['case_id']}/regressions")).json()
                result = next((row for row in compared if row["candidate_trial_id"] == regression_id), None)
                if result and "outcome" in result:
                    break
                await asyncio.sleep(.1)
            if not result or "outcome" not in result:
                raise RuntimeError("Controller regression did not finish")
            candidate_trial = (await client.get(f"/trials/{regression_id}")).json()
            if candidate_trial["status"] != "done" or not candidate_trial["metrics"]["robot_metrics"]:
                raise RuntimeError("Regression has no measured CPU policy trial")
            comparison = (await client.get("/comparisons", params={
                "baseline": case["baseline_trial_id"], "candidate": regression_id})).json()
            coverage = (await client.get("/benchmarks")).json()
            score = (await client.get("/safety-score")).json()
            if (not comparison["comparable"] or
                    "object_final_x_m" not in {row["name"] for row in comparison["metrics"]} or
                    coverage["backend_hazards"].get("mujoco_cpu") != ["object_positioning"] or
                    score["score_kind"] != "task_success_rate"):
                raise RuntimeError("CPU comparison/benchmark integration failed")
            print(f"Regression finished: {result['outcome']}", flush=True)
            report = {"hunt_id": hunt_id, "status": state["status"], "trials_executed": state["trials_executed"],
                    "failures_discovered": state["failures_discovered"], "case_id": case["case_id"],
                    "baseline_final_x_m": case["measured_metrics"]["robot_metrics"]["object_final_x_m"],
                    "baseline_policy_digest": case["policy"]["checkpoint_digest"],
                    "evidence_verification": verification["status"], "replay_status": repeated["status"],
                    "replay_final_x_m": replay_positions[0],
                    "regression_outcome": result["outcome"], "candidate_trial_id": regression_id,
                    "candidate_final_x_m": candidate_trial["metrics"]["robot_metrics"]["object_final_x_m"],
                    "candidate_policy_digest": candidate_trial["metrics"]["policy_checkpoint_digest"],
                    "reproduction_status": case["reproduction"]["status"],
                    "empirical_boundary": case["boundary"]["statement"] if case.get("boundary") else None,
                    "artifact_directory": str(bundle)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--strategy", choices=("adaptive", "grid", "random"), default="adaptive")
    parser.add_argument("--policy-id", default="gantry-push-v1")
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        print(json.dumps(asyncio.run(run(args.output.resolve(), args.trials, args.strategy, args.policy_id)), indent=2))
    else:
        with tempfile.TemporaryDirectory(prefix="ghost-cpu-") as directory:
            print(json.dumps(asyncio.run(run(Path(directory), args.trials, args.strategy, args.policy_id)), indent=2))


if __name__ == "__main__":
    main()
