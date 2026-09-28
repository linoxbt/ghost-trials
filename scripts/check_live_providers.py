"""Explicit, bounded provider verification. Does NOT execute a robot policy.

Run from the repository: .venv/bin/python -m scripts.check_live_providers
Add --judge to make up to three billable Nemotron calls on missing-evidence input.
No secrets, raw provider responses, or synthetic safety scores are printed.
"""
import argparse
import asyncio
import json

import httpx

from ghost_trials.adapters import NebiusNemotronJudge
from ghost_trials.config import Settings
from ghost_trials.models import Scenario, StructuredDescription, TrialMetrics


async def check(judge_test=False):
    settings = Settings()
    if not settings.nebius_api_key:
        raise RuntimeError("NEBIUS_API_KEY is missing")
    async with httpx.AsyncClient(base_url=settings.nebius_base_url, timeout=30) as client:
        response = await client.get("models", headers={"Authorization": f"Bearer {settings.nebius_api_key}"})
        response.raise_for_status()
    models = {m["id"] for m in response.json()["data"]}
    report = {
        "nebius_authenticated": True,
        "super_available": settings.nebius_super_model in models,
        "ultra_available": settings.nebius_ultra_model in models,
        "cosmos_credentials_present": bool(settings.cosmos_api_key or settings.nvidia_api_key),
        "cosmos_generation_verified": False,
        "robot_execution_verified": False,
    }
    if judge_test:
        if not report["super_available"] or not report["ultra_available"]:
            raise RuntimeError("Configured judge models are not available")
        scenario = Scenario(scenario_id="provider_probe_not_a_robot_trial", prompt="Missing telemetry provider connection test",
            structured_description=StructuredDescription(objects=[], hazard_type="falling_object",
                severity="medium", expected_safe_behavior="No policy has run; no evidence is available."),
            severity_tag="medium", seed=0)
        metrics = TrialMetrics(time_to_react_ms=None, min_clearance_m=None, task_completed=False,
            fall_or_collision=False, evidence_origin="unknown", measurements_are_proxies=True,
            metric_basis="Connection probe ONLY. No robot execution. All outcomes are unknown; required booleans are placeholders, not measurements.")
        result = await NebiusNemotronJudge(settings.model_copy(update={"ghost_model_max_tokens": 1024})).judge(scenario, metrics)
        if result.score_category.value != "insufficient_evidence":
            raise RuntimeError("Judge did not reject missing robot evidence")
        report.update(judge_inference_verified=True, probe_finding=result.score_category.value, tier_used=result.tier_used)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", action="store_true", help="Make bounded, billable judge inference calls")
    args = parser.parse_args()
    try:
        asyncio.run(check(args.judge))
    except Exception as exc:
        print(json.dumps({"verified": False, "error_type": type(exc).__name__}))
        raise SystemExit(1)
