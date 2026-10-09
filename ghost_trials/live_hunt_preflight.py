"""Read-only readiness check for a paid, evidence-backed Ghost Hunt.

This checks local configuration, not provider billing or GPU availability. It
never makes a provider call, submits a job, or treats an operator's confirmation
as independent proof of an external spending cap.
"""
from __future__ import annotations

import argparse
import json

from .config import Settings


def inspect(settings: Settings, max_trials: int) -> dict:
    if not 3 <= max_trials <= 50:
        raise ValueError("Hunt trial budget must be between 3 and 50")
    missing: list[str] = []
    expected = {"ghost_mode": "production", "ghost_scenario_provider": "cosmos",
                "ghost_simulator_provider": "isaac_http", "ghost_judge_provider": "nebius"}
    for field, value in expected.items():
        if getattr(settings, field) != value:
            missing.append(f"{field} must be {value}")
    if settings.cosmos_api_style == "nvidia_catalog":
        if not (settings.nvidia_api_key or settings.cosmos_api_key):
            missing.append("NVIDIA_API_KEY or COSMOS_API_KEY for hosted Cosmos")
        if settings.cosmos_num_frames < 25 or (settings.cosmos_num_frames - 1) % 4:
            missing.append("hosted Cosmos frame count must be at least 25 and follow 4k+1")
    elif not (settings.cosmos_base_url and settings.cosmos_api_key):
        missing.append("private Cosmos endpoint and key")
    for field, label in (("nebius_api_key", "Nebius judge key"),
                         ("isaac_job_endpoint", "GPU worker endpoint"),
                         ("isaac_job_token", "GPU worker token"),
                         ("gr00t_checkpoint", "compatible G1 policy checkpoint"),
                         ("gr00t_checkpoint_digest", "checkpoint digest")):
        if not getattr(settings, field):
            missing.append(label)
    if not (settings.scenario_reasoner_api_key or settings.nebius_api_key):
        missing.append("scenario reasoner key")
    if not settings.ghost_customer_auth_required:
        missing.append("customer authentication must be required")
    if not settings.ghost_provider_spending_controls_confirmed:
        missing.append("operator confirmation of provider-side spending controls")
    if not settings.ghost_live_execution_enabled:
        missing.append("explicit live-execution enablement")
    if settings.ghost_live_job_reservation_cents <= 0:
        missing.append("positive per-trial admission reservation")
    if settings.ghost_platform_budget_cents <= 0:
        missing.append("positive platform admission budget")
    worst_case_reservation = max_trials * settings.ghost_live_job_reservation_cents
    if settings.ghost_platform_budget_cents and worst_case_reservation > settings.ghost_platform_budget_cents:
        missing.append("platform admission budget is smaller than the full Hunt reservation")
    return {
        "ready_to_attempt_live_hunt": not missing,
        "missing_or_unconfirmed": missing,
        "maximum_trials": max_trials,
        "maximum_admission_reservation_cents": worst_case_reservation,
        "platform_admission_budget_cents": settings.ghost_platform_budget_cents,
        "organization_budget_checked": False,
        "external_provider_cap_independently_verified": False,
        "gpu_or_checkpoint_runtime_verified": False,
        "cosmos_generation_verified": False,
        "robot_trial_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-trials", type=int, default=3)
    args = parser.parse_args()
    try:
        result = inspect(Settings(), args.max_trials)
    except ValueError as exc:
        parser.exit(2, f"Invalid preflight request: {exc}\n")
    print(json.dumps(result, indent=2))
    if not result["ready_to_attempt_live_hunt"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
