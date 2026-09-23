from __future__ import annotations

import asyncio
import sys

import httpx

from .config import get_settings
from .production import CosmosVideoClient, ProductionConfigurationError, _auth_headers


async def main_async() -> int:
    settings = get_settings()
    failures: list[str] = []
    print("Ghost Trials production preflight")
    print(f"  mode: {settings.ghost_mode}")
    print(f"  execution backend: {settings.ghost_execution_backend}")
    try:
        cosmos = CosmosVideoClient(settings)
        ready = await cosmos.ready()
        print(f"  Cosmos: {'ready' if ready else 'unreachable'}")
        if not ready:
            failures.append("Cosmos readiness check failed")
    except ProductionConfigurationError as exc:
        failures.append(str(exc))
    reasoner_key = settings.scenario_reasoner_api_key or settings.nebius_api_key
    if not reasoner_key:
        failures.append("scenario reasoner API key is missing")
    else:
        try:
            async with httpx.AsyncClient(base_url=settings.scenario_reasoner_base_url, timeout=20) as client:
                response = await client.get("models", headers=_auth_headers(reasoner_key))
                response.raise_for_status()
                available = {model["id"] for model in response.json().get("data", [])}
            if settings.scenario_reasoner_model not in available:
                failures.append(f"scenario reasoner model is unavailable: {settings.scenario_reasoner_model}")
        except httpx.HTTPError as exc:
            failures.append(f"scenario reasoner model discovery failed: {exc}")
    if settings.ghost_judge_provider == "nebius" and not settings.nebius_api_key:
        failures.append("NEBIUS_API_KEY is missing for the judge")
    elif settings.ghost_judge_provider == "nebius" and settings.nebius_api_key:
        try:
            async with httpx.AsyncClient(base_url=settings.nebius_base_url, timeout=20) as client:
                response = await client.get("models", headers=_auth_headers(settings.nebius_api_key))
                response.raise_for_status()
                available = {model["id"] for model in response.json().get("data", [])}
            for model in (settings.nebius_super_model, settings.nebius_ultra_model):
                if model not in available:
                    failures.append(f"judge model is unavailable: {model}")
        except httpx.HTTPError as exc:
            failures.append(f"judge model discovery failed: {exc}")
    if not settings.isaac_job_endpoint:
        failures.append("ISAAC_JOB_ENDPOINT is missing")
    else:
        try:
            async with httpx.AsyncClient(base_url=settings.isaac_job_endpoint, timeout=10) as client:
                response = await client.get(
                    "v1/health/ready",
                    headers=_auth_headers(settings.isaac_job_token),
                )
                response.raise_for_status()
                worker = response.json()
            actual_backend = worker.get("backend")
            if actual_backend != settings.ghost_execution_backend:
                failures.append(
                    f"Isaac worker backend mismatch: {actual_backend} != {settings.ghost_execution_backend}"
                )
            if worker.get("policy_checkpoint_digest") != settings.gr00t_checkpoint_digest:
                failures.append("Isaac worker policy digest differs from GR00T_CHECKPOINT_DIGEST")
            if settings.isaac_worker_expected_commit and worker.get("worker_commit") != settings.isaac_worker_expected_commit:
                failures.append(
                    f"Isaac worker commit mismatch: {worker.get('worker_commit')} != {settings.isaac_worker_expected_commit}"
                )
            print(f"  Isaac worker: ready ({actual_backend or 'backend not reported'})")
        except httpx.HTTPError as exc:
            failures.append(f"Isaac worker readiness check failed: {exc}")
    if not settings.gr00t_checkpoint:
        failures.append("GR00T_CHECKPOINT is missing")
    if not settings.gr00t_checkpoint_digest:
        failures.append("GR00T_CHECKPOINT_DIGEST is missing; certificates would not identify the policy build")
    if failures:
        print("\nPreflight failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nAll configured services are ready.")
    return 0


def main() -> None:
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
