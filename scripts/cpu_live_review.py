"""Run one retained, measured CPU trial; optionally request one live Nemotron review.

No model call occurs unless both --live-nebius and --confirm-provider-limit are set.
The confirmation must mean credit-only billing or an actual provider-side hard limit;
the local reservation is not a guarantee about the external bill.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from ghost_trials.accounts import Accounts
from ghost_trials.config import Settings
from ghost_trials.cpu_evidence import CpuEvidenceRepository
from ghost_trials.cpu_review import CpuNemotronReviewer
from ghost_trials.cpu_robot import CpuMeasuredJudge, CpuMujocoSimulator, CpuScenarioGenerator
from ghost_trials.durable import DurableStore
from ghost_trials.models import ScenarioCreate, TrialStatus
from ghost_trials.pipeline import CertificationPipeline


async def run(output: Path, *, live_nebius: bool, seed: int = 42,
              env_file: Path | None = None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose a new, empty output directory; existing evidence is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    base = Settings(_env_file=env_file or ".env")
    settings = base.model_copy(update={
        "ghost_data_path": output / "state.sqlite3",
        "ghost_artifact_root": output / "artifacts",
        "ghost_cpu_model_review_enabled": live_nebius,
        "ghost_live_execution_enabled": live_nebius,
        "ghost_provider_spending_controls_confirmed": live_nebius,
        "ghost_platform_budget_cents": 10 if live_nebius else 0,
        "ghost_cpu_model_review_reservation_cents": 10,
        "ghost_cpu_model_review_max_tokens": 512,
    })
    if live_nebius:
        if not settings.nebius_api_key:
            raise RuntimeError("NEBIUS_API_KEY is missing; no provider request was made")
        async with httpx.AsyncClient(base_url=settings.nebius_base_url, timeout=20) as client:
            catalog = await client.get("models", headers={"Authorization": f"Bearer {settings.nebius_api_key}"})
            catalog.raise_for_status()
        if settings.nebius_super_model not in {row.get("id") for row in catalog.json().get("data", [])}:
            raise RuntimeError("Configured Nemotron Super model is not in the current catalog")

    store = DurableStore(settings.ghost_data_path)
    if live_nebius:
        Accounts(store, settings).allocate_budget("legacy", 10)
    simulator = CpuMujocoSimulator()

    async def publish(_event):
        return None

    pipeline = CertificationPipeline(store, CpuScenarioGenerator(), simulator,
                                     CpuMeasuredJudge(), publish, delay_seconds=0,
                                     embodiment="GHOST_GANTRY_XY", policy_name="gantry-push-v1")
    pipeline.require_robot_evidence = True
    pipeline.evidence_repository = CpuEvidenceRepository(settings)
    pipeline.model_reviewer = CpuNemotronReviewer(settings, store)
    _, trial = await pipeline.create(ScenarioCreate(
        prompt="A gantry robot arm pushes a block into a target band on a tabletop.", seed=seed))
    await pipeline.run(trial.trial_id)
    saved = store.trials[trial.trial_id]
    if (saved.status != TrialStatus.DONE or saved.evidence_verification.get("status") != "cpu_trace_metrics_verified"
            or not saved.metrics or not saved.metrics.robot_metrics):
        raise RuntimeError(f"No completed verified CPU trial: {saved.status}")
    review = saved.model_review
    report = {
        "trial_id": saved.trial_id,
        "status": saved.status.value,
        "simulator_version": saved.metrics.simulator_version,
        "policy_name": saved.policy_name,
        "checkpoint_digest": saved.metrics.policy_checkpoint_digest,
        "seed": seed,
        "task_completed": saved.metrics.task_completed,
        "object_final_x_m": saved.metrics.robot_metrics["object_final_x_m"],
        "simulation_duration_s": saved.metrics.robot_metrics["simulation_duration_s"],
        "evidence_verification": saved.evidence_verification["status"],
        "model_review_status": review.status if review else "missing",
        "model_id": review.model_id if review and review.status == "complete" else None,
        "model_suggestion": review.suggested_outcome if review and review.status == "complete" else None,
        "model_evidence_digest": review.evidence_digest if review and review.status == "complete" else None,
        "prompt_tokens": review.prompt_tokens if review and review.status == "complete" else None,
        "completion_tokens": review.completion_tokens if review and review.status == "complete" else None,
        "output_directory": str(output.resolve()),
    }
    (output / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n")
    if live_nebius and (not review or review.status != "complete"):
        raise RuntimeError(f"Measured trial {saved.trial_id} completed, but live Nemotron review did not: "
                           f"{review.status if review else 'missing'}; evidence retained in {output}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the SQLite record and artifacts")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env-file", type=Path, help="Private configuration file; never copied into output")
    parser.add_argument("--live-nebius", action="store_true", help="Make at most one billable Nemotron request")
    parser.add_argument("--confirm-provider-limit", action="store_true",
                        help="Confirm credit-only billing or a real provider-side hard spending limit")
    args = parser.parse_args()
    if args.live_nebius != args.confirm_provider_limit:
        parser.error("--live-nebius and --confirm-provider-limit must be supplied together")
    print(json.dumps(asyncio.run(run(args.output, live_nebius=args.live_nebius,
                                     seed=args.seed, env_file=args.env_file)), indent=2))


if __name__ == "__main__":
    main()
