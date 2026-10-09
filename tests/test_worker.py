import asyncio
import json
import sys
import time

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from workers.isaac import service
from workers.isaac.hazards import compile_hazard
from workers.isaac.trial_runner import derive_metrics


@pytest.fixture
def worker(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "output_root", tmp_path)
    monkeypatch.setattr(service.settings, "token", "test-secret")
    monkeypatch.setattr(service.settings, "backend", "gear_sonic_sim")
    monkeypatch.setattr(service.settings, "require_gpu", False)
    monkeypatch.setattr(service.settings, "require_policy", False)
    monkeypatch.setattr(service.settings, "runner_command", sys.executable)
    monkeypatch.setenv("GEAR_SONIC_SIM_COMMAND", sys.executable)
    monkeypatch.setattr(service, "execution_lock", asyncio.Lock())
    service.jobs.clear()
    return service


@pytest.mark.asyncio
async def test_worker_auth_and_missing_backend(worker, monkeypatch):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url="http://worker") as client:
        assert (await client.get("/v1/health/ready")).status_code == 401
        monkeypatch.delenv("GEAR_SONIC_SIM_COMMAND")
        response = await client.get("/v1/health/ready", headers={"Authorization": "Bearer test-secret"})
        assert response.status_code == 503
        assert "hazard runner" in response.text


@pytest.mark.asyncio
async def test_only_signed_artifacts_are_served(worker):
    directory = worker.settings.output_root / "isaac_123"
    directory.mkdir()
    (directory / "telemetry.jsonl").write_text('{"sample":1}\n')
    (directory / "request.json").write_text('{"private":"configuration"}')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url="http://worker") as client:
        assert (await client.get("/artifacts/isaac_123/request.json")).status_code == 404
        assert (await client.get("/artifacts/isaac_123/telemetry.jsonl")).status_code == 403
        expires = int(time.time()) + 60
        signature = worker.artifact_signature("isaac_123", "telemetry.jsonl", expires)
        response = await client.get(f"/artifacts/isaac_123/telemetry.jsonl?expires={expires}&signature={signature}")
        assert response.status_code == 200
        assert response.json() == {"sample": 1}


@pytest.mark.asyncio
async def test_unconfigured_token_fails_closed(worker, monkeypatch):
    monkeypatch.setattr(worker.settings, "token", None)
    monkeypatch.setattr(worker.settings, "allow_unauthenticated", False)
    with pytest.raises(HTTPException) as exc:
        worker.authorize(None)
    assert exc.value.status_code == 503


def sample(**values):
    return {"timestamp_ms": 1000, "hazard_active": True, "policy_reacted": False,
            "clearance_m": 0.4, "collision": False, "fall": False, **values}


def test_no_reaction_is_not_a_fabricated_latency(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text("\n".join(json.dumps(r) for r in [sample(intervention=True), sample(timestamp_ms=1500, intervention=True)]))
    metrics = derive_metrics(trace, {"policy": {}})
    assert metrics.time_to_react_ms is None
    assert metrics.observation_window_ms == 500
    assert metrics.intervention_count == 1


@pytest.mark.parametrize("bad", [{"clearance_m": float("nan")}, {"collision": "false"}, {"timestamp_ms": -1}])
def test_invalid_evidence_is_rejected(tmp_path, bad):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps(sample(**bad)))
    with pytest.raises(ValidationError):
        derive_metrics(trace, {"policy": {}})


def test_trace_time_cannot_go_backwards(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps(sample()) + "\n" + json.dumps(sample(timestamp_ms=500)))
    with pytest.raises(RuntimeError, match="strictly increasing"):
        derive_metrics(trace, {"policy": {}})


def test_hazard_recipe_replay_and_unsupported_type():
    scenario = {"seed": 42, "severity_tag": "high", "structured_description": {"hazard_type": "falling_object"}}
    assert compile_hazard(scenario) == compile_hazard(scenario)
    scenario["structured_description"]["hazard_type"] = "human_intrusion"
    with pytest.raises(ValueError, match="Unsupported executable hazard"):
        compile_hazard(scenario)


@pytest.mark.asyncio
async def test_worker_rejects_unsupported_parameterized_recipe_before_launch(worker):
    scenario = {"scenario_id": "s1", "prompt": "A box falls into the path", "seed": 5,
                "severity_tag": "medium", "structured_description": {"objects": ["box"],
                "hazard_type": "falling_object", "severity": "medium", "expected_safe_behavior": "Avoid the box"}}
    recipe = compile_hazard(scenario).to_dict()
    recipe["robot_velocity_m_s"] = 2.0
    scenario["execution_recipe"] = recipe
    request = {"scenario": scenario, "execution_backend": "gear_sonic_sim", "embodiment": "UNITREE_G1_SONIC",
               "policy": {"checkpoint": "fixture", "checkpoint_digest": "sha256:test", "host": "127.0.0.1", "port": 5550}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url="http://worker") as client:
        response = await client.post("/v1/jobs", json=request, headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 422
    assert "invalid hazard recipe" in response.text.lower()
    assert not worker.jobs


@pytest.mark.asyncio
async def test_timeout_terminates_runner_before_next_job(worker, monkeypatch, tmp_path):
    # A real child process validates timeout cleanup; it never loads GPU code.
    script = tmp_path / "slow_runner.py"
    script.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(worker.settings, "runner_command", f"{sys.executable} {script}")
    monkeypatch.setattr(worker.settings, "timeout", 0.1)
    request = worker.IsaacJobRequest.model_validate({
        "scenario": {"scenario_id": "scn_1", "prompt": "A box falls", "seed": 42, "severity_tag": "high",
                     "structured_description": {"objects": ["box"], "hazard_type": "falling_object", "severity": "high", "expected_safe_behavior": "Avoid box"}},
        "execution_backend": "gear_sonic_sim", "embodiment": "UNITREE_G1_SONIC",
        "policy": {"checkpoint": "/models/test", "host": "127.0.0.1", "port": 5550},
    })
    worker.jobs["isaac_test"] = {"job_id": "isaac_test", "status": "queued"}
    worker.save_job("isaac_test")
    await asyncio.wait_for(worker.execute("isaac_test", request), 8)
    assert worker.jobs["isaac_test"]["status"] == "failed"
    assert not worker.execution_lock.locked()
