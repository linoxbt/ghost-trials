"""Regression tests for the deep-review findings fixed together (planner, scoring, evidence, ops)."""
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from ghost_trials import bundle_cache, hunt as hunt_module
from ghost_trials.cpu_evidence import verify_cpu_bundle
from ghost_trials.evaluation import guard_judgment
from ghost_trials.execution_setup import directory_digest
from ghost_trials.hunt import GhostCase, ReproductionResult, compare_case_regression
from ghost_trials.models import JudgeResult, ScoreCategory
from test_failure_reproduction import checked_trial
from test_hunt import cpu_hunt, hunt, run_oracle

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "static" / "reference" / "gantry-v1"


def test_adaptive_hunt_never_reruns_an_executed_recipe():
    for index in range(40):
        h = cpu_hunt(budget=50)
        h.hunt_id = f"hunt_dup_{index}"
        run_oracle(h, lambda c: c["object_mass_kg"] > .3 or c["controller_delay_s"] > 1.0)
        seen = [(c.seed, tuple(sorted(c.controls.items()))) for c in h.candidates if c.phase != "reproduce"]
        assert len(seen) == len(set(seen)), h.hunt_id


def _case(status):
    return GhostCase(case_id="case1", hunt_id="hunt1", organization_id="org_a", baseline_trial_id="base",
                     scenario_id="s1", execution_recipe={"version": "v1"}, seed=3, environment="warehouse",
                     policy=hunt().policy, simulator_version="mujoco-test", rubric_version="warehouse-evaluation-v3",
                     measured_metrics={}, evidence_verification={}, artifact_manifest={},
                     recording_url="/video.mp4", telemetry_url="/trace.jsonl",
                     reproduction=ReproductionResult(status=status))


@pytest.mark.parametrize("status,outcome", [("reproducible", "fixed_on_case"), ("flaky", "incompatible_or_unverified"),
                                            ("not_reproduced", "incompatible_or_unverified")])
def test_regression_requires_a_baseline_that_reliably_fails(monkeypatch, status, outcome):
    monkeypatch.setattr(hunt_module, "compare_trials", lambda *args: {"warnings": []})
    candidate = checked_trial("candidate", False)
    candidate.metrics.policy_checkpoint_digest = "sha256:new"
    case = _case(status)
    scenario = type("S", (), {"execution_recipe": case.execution_recipe, "structured_description": None})()
    monkeypatch.setattr(hunt_module, "observed_outcome", lambda trial, scenario=None: ("pass", ""))
    result = compare_case_regression(case, checked_trial("base", True), candidate, scenario, scenario)
    assert result.outcome == outcome and result.baseline_reproduction == status


def test_cpu_collision_fails_even_when_block_lands_in_band():
    summary = json.loads((REFERENCE / "summary.json").read_text())
    from ghost_trials.models import Scenario, StructuredDescription, Trial, TrialMetrics, TrialStatus
    scenario = Scenario(scenario_id="s", prompt="position a block", seed=1, severity_tag="medium",
                        structured_description=StructuredDescription(objects=["block"], hazard_type="object_positioning",
                                                                     severity="medium", expected_safe_behavior="band"))
    trial = Trial(trial_id="t", scenario_id="s", status=TrialStatus.DONE, embodiment="GHOST_GANTRY_XY",
                  metrics=TrialMetrics(time_to_react_ms=1, min_clearance_m=None, task_completed=True, fall_or_collision=True,
                                       evidence_origin="simulator", robot_metrics=summary))
    import ghost_trials.evaluation as evaluation
    original = evaluation.evidence_report, evaluation.evidence_class
    try:
        evaluation.evidence_report = lambda *a: {"missing_evidence": []}
        evaluation.evidence_class = lambda *a: "artifact_validated_simulation"
        result = guard_judgment(trial, scenario, JudgeResult(score_category=ScoreCategory.AVOIDED, confidence=1,
                                                             reasoning_trace="x", tier_used="cpu-measured-rubric-v1"))
    finally:
        evaluation.evidence_report, evaluation.evidence_class = original
    assert result.score_category == ScoreCategory.FAILED


def _rehash(bundle: Path, summary: dict):
    data = json.dumps(summary).encode()
    (bundle / "summary.json").write_bytes(data)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["summary.json"] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (bundle / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("field,value", [("max_contact_force_n", 0.0), ("pusher_object_contact_count", 0),
                                         ("max_block_tilt_deg", 0.0), ("object_initial_x_m", 0.41)])
def test_cpu_bundle_rejects_summary_inconsistent_with_trace(tmp_path, field, value):
    bundle = tmp_path / "bundle"
    shutil.copytree(REFERENCE, bundle)
    summary = json.loads((bundle / "summary.json").read_text())
    assert verify_cpu_bundle(bundle, summary["policy_digest"])["status"] == "cpu_trace_metrics_verified"
    summary[field] = value
    _rehash(bundle, summary)
    with pytest.raises(ValueError):
        verify_cpu_bundle(bundle, summary["policy_digest"])


def test_cached_json_decode_failure_keeps_failing_closed(tmp_path):
    (tmp_path / "manifest.json").write_text("{broken")
    bundle_cache.clear()
    for _ in range(2):
        with pytest.raises(ValueError):
            bundle_cache.cached_verification("cpu", tmp_path, "d", verify_cpu_bundle)


def test_checkpoint_digest_matches_shell_script(tmp_path):
    for name, content in {"a/b": "1", "a-b": "2", "B/z": "3", "_x": "4", "é": "5"}.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    shell = subprocess.run(["bash", str(ROOT / "scripts" / "checkpoint_digest.sh"), str(tmp_path)],
                           check=True, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"})
    assert shell.stdout.strip() == directory_digest(tmp_path)


def test_telemetry_schema_documents_every_enforced_field():
    from workers.isaac.trial_runner import TelemetrySample
    schema = json.loads((ROOT / "workers" / "isaac" / "telemetry.schema.json").read_text())
    assert set(schema["properties"]) == set(TelemetrySample.model_fields)


@pytest.mark.asyncio
async def test_development_mode_refuses_cross_site_writes():
    from ghost_trials.app import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/ops/maintenance", content='{"enabled": true}',
                                     headers={"Origin": "https://attacker.example", "Content-Type": "text/plain"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_monitor_does_not_alert_on_old_failures():
    from ghost_trials.monitor import check
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "database_ok": True, "runner_alive": True, "jobs": {"states": {"error": 3}, "errors_last_hour": 0}}))
    async with httpx.AsyncClient(transport=transport) as client:
        assert await check(client, "https://api.test", "token") == []


@pytest.fixture
def policy_worker(tmp_path, monkeypatch):
    from workers.isaac import service
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    monkeypatch.setattr(service.settings, "output_root", tmp_path / "out")
    monkeypatch.setattr(service.settings, "token", "test-secret")
    monkeypatch.setattr(service.settings, "backend", "gear_sonic_sim")
    monkeypatch.setattr(service.settings, "require_gpu", False)
    monkeypatch.setattr(service.settings, "require_policy", True)
    monkeypatch.setattr(service.settings, "runner_command", sys.executable)
    monkeypatch.setattr(service.settings, "checkpoint", str(checkpoint))
    monkeypatch.setattr(service.settings, "checkpoint_digest", directory_digest(checkpoint))
    monkeypatch.setattr(service.settings, "policy_host", "127.0.0.1")
    monkeypatch.setenv("GEAR_SONIC_SIM_COMMAND", sys.executable)
    service.jobs.clear()
    return service, checkpoint


@pytest.mark.asyncio
async def test_worker_measures_checkpoint_and_pins_policy_server(policy_worker, monkeypatch):
    service, checkpoint = policy_worker
    server = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(service.settings, "policy_port", port)
    headers = {"Authorization": "Bearer test-secret"}
    request = {"scenario": {"scenario_id": "scn_1", "prompt": "A box falls", "seed": 42, "severity_tag": "high",
                            "structured_description": {"objects": ["box"], "hazard_type": "falling_object", "severity": "high",
                                                       "expected_safe_behavior": "Avoid box"}},
               "execution_backend": "gear_sonic_sim", "embodiment": "UNITREE_G1_SONIC",
               "policy": {"checkpoint": str(checkpoint), "checkpoint_digest": service.settings.checkpoint_digest,
                          "host": "10.0.0.9", "port": port}}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url="http://worker") as client:
            assert (await client.get("/v1/health/ready", headers=headers)).status_code == 200
            response = await client.post("/v1/jobs", json=request, headers=headers)
            assert response.status_code == 422 and "policy server" in response.text
            (checkpoint / "model.safetensors").write_bytes(b"swapped weights")
            response = await client.get("/v1/health/ready", headers=headers)
            assert response.status_code == 503 and "does not match" in response.text
    finally:
        server.close()
        await server.wait_closed()
    assert not service.jobs
