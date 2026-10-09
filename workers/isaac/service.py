"""HTTP job service to run on the Isaac/GR00T GPU node."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import shlex
import shutil
import signal
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ghost_trials.models import Scenario, TrialMetrics
from workers.isaac.hazards import compile_hazard, supported_controls


class PolicySpec(BaseModel):
    checkpoint: str
    checkpoint_digest: str | None = None
    host: str
    port: int
    action_horizon: int = Field(default=40, ge=1, le=40)


class IsaacJobRequest(BaseModel):
    scenario: Scenario
    execution_backend: str
    embodiment: str
    policy: PolicySpec


class WorkerSettings:
    token = os.getenv("ISAAC_WORKER_TOKEN")
    output_root = Path(os.getenv("ISAAC_WORKER_OUTPUT_ROOT", "artifacts/worker"))
    public_base_url = os.getenv("ISAAC_WORKER_PUBLIC_BASE_URL", "http://127.0.0.1:9000").rstrip("/")
    runner_command = os.getenv("ISAAC_RUNNER_COMMAND", "python /app/workers/isaac/trial_runner.py")
    timeout = float(os.getenv("ISAAC_RUNNER_TIMEOUT_SECONDS", "1800"))
    backend = os.getenv("ISAAC_WORKER_BACKEND", "gear_sonic_sim")
    require_gpu = os.getenv("ISAAC_WORKER_REQUIRE_GPU", "true").lower() in {"1", "true", "yes"}
    require_policy = os.getenv("ISAAC_WORKER_REQUIRE_POLICY", "true").lower() in {"1", "true", "yes"}
    policy_host = os.getenv("GR00T_POLICY_HOST", "127.0.0.1")
    policy_port = int(os.getenv("GR00T_POLICY_PORT", "5550"))
    build_commit = os.getenv("GHOST_WORKER_COMMIT", "unknown")
    checkpoint = os.getenv("GR00T_CHECKPOINT")
    checkpoint_digest = os.getenv("GR00T_CHECKPOINT_DIGEST")
    allow_unauthenticated = os.getenv("ISAAC_WORKER_ALLOW_UNAUTHENTICATED", "false").lower() in {
        "1", "true", "yes"
    }


settings = WorkerSettings()
app = FastAPI(title="Ghost Trials Isaac Worker", version="1.0")
jobs: dict[str, dict] = {}
execution_lock = asyncio.Lock()


def artifact_signature(job_id: str, filename: str, expires: int) -> str:
    return hmac.new((settings.token or "").encode(), f"{job_id}/{filename}:{expires}".encode(), hashlib.sha256).hexdigest()


async def stop_process(process) -> None:
    # Kill the session, including simulator children, before releasing the GPU lock.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), 5)
    except TimeoutError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


def authorize(authorization: str | None) -> None:
    if not settings.token:
        if settings.allow_unauthenticated:
            return
        raise HTTPException(503, "Worker token is not configured")
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not secrets.compare_digest(supplied, settings.token):
        raise HTTPException(401, "Invalid worker token")


def save_job(job_id: str) -> None:
    job_dir = settings.output_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    temporary = job_dir / "job.tmp"
    temporary.write_text(json.dumps(jobs[job_id], indent=2))
    temporary.replace(job_dir / "job.json")


async def execute(job_id: str, request: IsaacJobRequest) -> None:
    job_dir = settings.output_root / job_id
    request_path = job_dir / "request.json"
    result_path = job_dir / "result.json"
    request_path.write_text(request.model_dump_json(indent=2))
    command = [*shlex.split(settings.runner_command), "--request", str(request_path), "--output", str(job_dir)]
    log_path = job_dir / "runner.log"
    try:
        # Isaac/SONIC processes own the GPU and DDS/ZMQ ports. Serialize jobs unless
        # a future worker implementation explicitly provides process isolation.
        async with execution_lock:
            jobs[job_id].update(status="running", started_at=datetime.now(timezone.utc).isoformat())
            save_job(job_id)
            with log_path.open("wb") as log:
                process = await asyncio.create_subprocess_exec(
                    *command, stdout=log, stderr=asyncio.subprocess.STDOUT, start_new_session=True
                )
                try:
                    await asyncio.wait_for(process.wait(), timeout=settings.timeout)
                finally:
                    await stop_process(process)
        if process.returncode != 0:
            raise RuntimeError(f"runner exited with status {process.returncode}; inspect runner.log")
        if not result_path.is_file():
            raise RuntimeError("runner did not produce result.json")
        raw = json.loads(result_path.read_text())
        metrics = TrialMetrics.model_validate(raw["metrics"])
        for field in ("simulation_video_url", "trace_url"):
            value = getattr(metrics, field)
            expected = "simulation.mp4" if field == "simulation_video_url" else "telemetry.jsonl"
            if value != expected:
                raise RuntimeError(f"Runner must supply local {expected}")
            artifact = (job_dir / value).resolve()
            if artifact.parent != job_dir.resolve() or not artifact.is_file() or artifact.stat().st_size == 0:
                raise RuntimeError(f"invalid or missing worker artifact: {value}")
            setattr(metrics, field, f"{settings.public_base_url}/artifacts/{job_id}/{value}")
        jobs[job_id].update(
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result={"metrics": metrics.model_dump(mode="json"), "artifacts": raw.get("artifacts", {})},
        )
    except Exception as exc:
        jobs[job_id].update(
            status="failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc) or type(exc).__name__,
        )
    save_job(job_id)


@app.get("/v1/health/ready")
async def ready(authorization: str | None = Header(default=None)):
    authorize(authorization)
    failures = []
    try:
        runner_parts = shlex.split(settings.runner_command)
    except ValueError:
        runner_parts = []
    runner = runner_parts[0] if runner_parts else ""
    if not runner or not shutil.which(runner):
        failures.append(f"runner executable not found: {runner}")
    if settings.require_gpu and shutil.which("nvidia-smi") is None:
        failures.append("nvidia-smi is unavailable")
    elif settings.require_gpu:
        probe = await asyncio.create_subprocess_exec(
            "nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(probe.communicate(), 5)
            if probe.returncode or not stdout.strip():
                failures.append("No NVIDIA GPU is visible")
        except TimeoutError:
            probe.kill()
            await probe.wait()
            failures.append("NVIDIA driver probe timed out")
    variable = "ISAAC_ARENA_COMMAND" if settings.backend == "isaac_arena_gr00t" else "GEAR_SONIC_SIM_COMMAND"
    command = shlex.split(os.getenv(variable, ""))
    if not command or not shutil.which(command[0]):
        failures.append(f"{variable} must point to an installed hazard runner")
    if settings.require_policy:
        if not settings.checkpoint or not settings.checkpoint_digest:
            failures.append("GR00T_CHECKPOINT and GR00T_CHECKPOINT_DIGEST must identify the served policy")
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(settings.policy_host, settings.policy_port), 2)
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError):
            failures.append(f"GR00T policy server is unreachable at {settings.policy_host}:{settings.policy_port}")
    if failures:
        raise HTTPException(503, detail={"status": "not_ready", "failures": failures})
    return {
        "status": "ready",
        "backend": settings.backend,
        "runner_command": runner,
        "output_root": str(settings.output_root),
        "worker_commit": settings.build_commit,
        "policy_checkpoint_digest": settings.checkpoint_digest,
        "gpu_required": settings.require_gpu,
        "policy_required": settings.require_policy,
    }


@app.post("/v1/jobs", status_code=202)
async def submit(
    request: IsaacJobRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    if request.execution_backend not in {"isaac_arena_gr00t", "gear_sonic_sim"}:
        raise HTTPException(422, "Unsupported execution backend")
    if request.execution_backend != settings.backend:
        raise HTTPException(422, f"Worker is pinned to {settings.backend}")
    if request.scenario.structured_description.hazard_type == "surface_instability" and settings.backend != "gear_sonic_sim":
        raise HTTPException(422, "Reduced traction requires gear_sonic_sim; Arena material updates are not validated")
    try:
        supported_controls(request.scenario.structured_description.hazard_type, settings.backend)
        compile_hazard(request.scenario.model_dump(mode="json"))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Unsupported or invalid hazard recipe: {exc}") from exc
    expected_embodiment = (
        "UNITREE_G1_SONIC" if request.execution_backend == "gear_sonic_sim" else "G1_WBC_JOINT"
    )
    if request.embodiment != expected_embodiment:
        raise HTTPException(
            422,
            f"{request.execution_backend} requires {expected_embodiment}; refusing to mislabel the run",
        )
    await ready(authorization)
    if settings.require_policy and (request.policy.checkpoint != settings.checkpoint or request.policy.checkpoint_digest != settings.checkpoint_digest):
        raise HTTPException(422, "Requested policy does not match the worker's served checkpoint")
    job_id = f"isaac_{uuid.uuid4().hex[:12]}"
    jobs[job_id] = {"job_id": job_id, "status": "queued", "error": None, "result": None}
    save_job(job_id)
    background_tasks.add_task(execute, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if not job_id.startswith("isaac_") or not job_id[6:].isalnum():
        raise HTTPException(404, "Job not found")
    if job_id not in jobs:
        path = settings.output_root / job_id / "job.json"
        if not path.is_file():
            raise HTTPException(404, "Job not found")
        jobs[job_id] = json.loads(path.read_text())
    job = json.loads(json.dumps(jobs[job_id]))
    if job.get("result"):
        expires = int(time.time()) + 7 * 24 * 3600
        job["result"]["artifact_urls"] = {
            filename: f"{settings.public_base_url}/artifacts/{job_id}/{filename}?expires={expires}&signature={artifact_signature(job_id, filename, expires)}"
            for filename in ("simulation.mp4", "telemetry.jsonl", "recipe.json")
            if filename in job["result"].get("artifacts", {})
        }
        for field, filename in (("simulation_video_url", "simulation.mp4"), ("trace_url", "telemetry.jsonl")):
            signature = artifact_signature(job_id, filename, expires)
            job["result"]["metrics"][field] = (
                f"{settings.public_base_url}/artifacts/{job_id}/{filename}?expires={expires}&signature={signature}"
            )
    return job


@app.get("/artifacts/{job_id}/{filename}")
async def artifact(job_id: str, filename: str, expires: int = 0, signature: str = ""):
    if filename not in {"simulation.mp4", "telemetry.jsonl", "recipe.json"} or not job_id.startswith("isaac_") or not job_id[6:].isalnum():
        raise HTTPException(404, "Artifact not found")
    if not settings.token or expires < time.time() or not hmac.compare_digest(signature, artifact_signature(job_id, filename, expires)):
        raise HTTPException(403, "Artifact link is missing, invalid, or expired; refresh the job")
    path = (settings.output_root / job_id / filename).resolve()
    if path.parent != (settings.output_root / job_id).resolve() or not path.is_file():
        raise HTTPException(404, "Artifact not found")
    media = "video/mp4" if filename.endswith("mp4") else "application/json" if filename.endswith("json") else "application/x-ndjson"
    return FileResponse(path, media_type=media)
