"""Verify Token Factory access without exposing secrets; inference is opt-in."""
import argparse
import asyncio
import json
from pathlib import Path

import httpx

from .adapters import JUDGE_SYSTEM_PROMPT
from .config import get_settings
from .models import JudgeResult


async def check(judge_test=False, transport=None):
    settings = get_settings()
    if not settings.nebius_api_key:
        raise ValueError("Save NEBIUS_API_KEY in the private .env first")
    async with httpx.AsyncClient(base_url=settings.nebius_base_url, timeout=120, transport=transport) as client:
        headers = {"Authorization": f"Bearer {settings.nebius_api_key}"}
        response = await client.get("models", headers=headers)
        response.raise_for_status()
        available = sorted(m["id"] for m in response.json()["data"] if "nemotron" in m["id"].lower())
        report = {"authenticated": True, "nemotron_models": available, "inference_test": "not_run",
                  "robot_execution_validated": False, "gpu_provisioned": False}
        if judge_test:
            if settings.nebius_super_model not in available:
                raise ValueError("Configured NEBIUS_SUPER_MODEL is not in your model catalog")
            response = await client.post("chat/completions", headers=headers, json={
                "model": settings.nebius_super_model, "temperature": .1, "max_tokens": 2048,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                             {"role": "user", "content": json.dumps({
                                 "purpose": "Connectivity test using synthetic fixture data, not an actual robot trial",
                                 "rubric_thresholds": {"reaction_ms": 500, "clearance_m": .5},
                                 "metrics": {"evidence_origin": "synthetic", "time_to_react_ms": None,
                                             "min_clearance_m": None, "task_completed": False,
                                             "fall_or_collision": False, "metric_basis": "No telemetry captured"}})}]})
            response.raise_for_status()
            body = response.json()
            raw = json.loads(body["choices"][0]["message"]["content"])
            result = JudgeResult.model_validate({**raw, "tier_used": settings.nebius_super_model})
            report.update(inference_test="passed", judge=result.model_dump(mode="json"), usage=body.get("usage"))
            if result.score_category.value != "insufficient_evidence":
                report["inference_test"] = "schema_passed_semantic_review_required"
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge-test", action="store_true", help="Make one small billed inference request using synthetic test data")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = asyncio.run(check(args.judge_test))
    except (ValueError, httpx.HTTPError, KeyError) as exc:
        # Never dump response bodies or authorization headers in a failure report.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "http_status": exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None}))
        raise SystemExit(1)
    output = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as stream:
            stream.write(output)
    print(output)


if __name__ == "__main__":
    main()
