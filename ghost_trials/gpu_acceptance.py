"""Preflight a configured worker; opt in to ONE GPU trial and download its evidence.

Does not provision compute, generate Cosmos video, or invoke a paid judge.
--execute consumes the configured worker's compute. It is not a monetary cap.
"""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .independent_validation import verify_bundle
from .models import Scenario, StructuredDescription
from .production import IsaacRemoteSimulator
from workers.isaac.hazards import compile_hazard


def artifact_origin(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid artifact origin")
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


async def acceptance(execute=False, output=None, hazard="surface_instability", max_bytes=1_000_000_000, transport=None):
    settings = get_settings()
    required = {"ISAAC_JOB_ENDPOINT": settings.isaac_job_endpoint, "ISAAC_JOB_TOKEN": settings.isaac_job_token,
                "GR00T_CHECKPOINT": settings.gr00t_checkpoint, "GR00T_CHECKPOINT_DIGEST": settings.gr00t_checkpoint_digest}
    missing = [key for key, value in required.items() if not value]
    if missing:
        return {"status": "blocked", "missing": missing, "gpu_trial_executed": False}
    if execute and (output is None or output.exists() or max_bytes <= 0):
        raise ValueError("Execution requires a new --output directory and positive artifact byte limit")
    if hazard == "surface_instability" and settings.ghost_execution_backend != "gear_sonic_sim":
        raise ValueError("Reduced traction currently requires the gear_sonic_sim backend")
    worker_origin = artifact_origin(settings.isaac_job_endpoint)
    headers = {"Authorization": f"Bearer {settings.isaac_job_token}"}
    async with httpx.AsyncClient(base_url=settings.isaac_job_endpoint, timeout=30, transport=transport) as client:
        response = await client.get("v1/health/ready", headers=headers)
        response.raise_for_status()
        ready = response.json()
    if ready.get("status") != "ready" or ready.get("backend") != settings.ghost_execution_backend:
        raise ValueError("Worker readiness/backend mismatch")
    if ready.get("gpu_required") is not True or ready.get("policy_required") is not True:
        raise ValueError("Acceptance requires worker GPU and policy checks enabled")
    if ready.get("policy_checkpoint_digest") != settings.gr00t_checkpoint_digest:
        raise ValueError("Worker checkpoint identity mismatch")
    if settings.isaac_worker_expected_commit and ready.get("worker_commit") != settings.isaac_worker_expected_commit:
        raise ValueError("Worker build identity mismatch")
    if not execute:
        return {"status": "preflight_passed", "worker": ready, "gpu_trial_executed": False}
    scenario = Scenario(scenario_id="acceptance_seed42", seed=42, severity_tag="medium",
        prompt=f"Acceptance test: {hazard}; fixed seed 42.",
        structured_description=StructuredDescription(objects=["robot", "warehouse"], hazard_type=hazard,
            severity="medium", expected_safe_behavior="Stay upright and avoid collision; inspect the captured evidence."))
    scenario.execution_recipe = compile_hazard(scenario.model_dump(mode="json")).to_dict()
    # Reserve the output before executing so an existing report is never overwritten.
    output.mkdir(parents=True, exist_ok=False)
    (output / "scenario.json").write_text(scenario.model_dump_json(indent=2))
    simulator = IsaacRemoteSimulator(settings, transport=transport)
    await simulator.run(scenario)
    result = simulator.last_result
    manifest = result.get("artifacts", {})
    allowed = {"simulation.mp4", "telemetry.jsonl", "recipe.json"}
    if set(manifest) != allowed:
        raise ValueError("Worker must provide exactly the recording, telemetry and recipe artifacts")
    total = 0
    async with httpx.AsyncClient(timeout=120, transport=transport, follow_redirects=False) as client:
        for name, record in manifest.items():
            size = record.get("bytes")
            if type(size) is not int or size <= 0 or total + size > max_bytes:
                raise ValueError("Artifact manifest exceeds download bounds")
            url = result.get("artifact_urls", {}).get(name)
            if not url or artifact_origin(url) != worker_origin:
                raise ValueError("Artifact must be a signed URL on the configured worker origin")
            written = 0
            # Signed URLs, never forward the worker bearer token to artifact URLs.
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with (output / name).open("xb") as stream:
                    async for chunk in response.aiter_bytes():
                        written += len(chunk)
                        if written > size:
                            raise ValueError("Artifact exceeds declared size")
                        stream.write(chunk)
            if written != size:
                raise ValueError("Truncated artifact")
            total += written
    # Do not persist signed URLs in the export intended for independent reviewers.
    metrics = dict(result["metrics"])
    metrics.update(simulation_video_url="simulation.mp4", trace_url="telemetry.jsonl")
    (output / "result.json").write_text(json.dumps({"metrics": metrics, "artifacts": manifest}, indent=2))
    validation = verify_bundle(output, settings.gr00t_checkpoint_digest)
    report = {"status": "worker_trial_and_integrity_checks_passed", "gpu_trial_executed": True,
              "worker": ready, "validation": validation, "independent_human_review": "not_performed"}
    (output / "acceptance.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run one trial on your already provisioned GPU worker")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--hazard", choices=["surface_instability", "falling_object", "path_obstruction"], default="surface_instability")
    parser.add_argument("--max-artifact-mb", type=int, default=1000)
    args = parser.parse_args()
    try:
        report = asyncio.run(acceptance(args.execute, args.output, args.hazard, args.max_artifact_mb * 1_000_000))
        print(json.dumps(report, indent=2))
        if report["status"] == "blocked":
            raise SystemExit(1)
    except (ValueError, OSError, RuntimeError, KeyError, httpx.HTTPError) as exc:
        # Avoid printing signed artifact links or response bodies on error.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, ValueError) else "Check worker logs and private configuration"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
