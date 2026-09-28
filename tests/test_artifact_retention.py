import hashlib
import json
import subprocess

import httpx
import pytest

from ghost_trials.artifacts import EvidenceRepository
from ghost_trials.config import Settings
from ghost_trials.models import Scenario, StructuredDescription, Trial
from workers.isaac.hazards import compile_hazard
from workers.isaac.trial_runner import derive_metrics


def evidence_fixture(tmp_path):
    scenario = Scenario(scenario_id="scn_evidence", seed=42, severity_tag="medium", prompt="A box falls from a shelf",
        structured_description=StructuredDescription(objects=["box", "robot"], hazard_type="falling_object",
            severity="medium", expected_safe_behavior="Avoid collision"))
    scenario.execution_recipe = compile_hazard(scenario.model_dump(mode="json")).to_dict()
    onset = int(scenario.execution_recipe["onset_s"] * 1000)
    rows = [{"timestamp_ms": onset + offset, "hazard_active": True, "policy_reacted": offset > 0,
             "clearance_m": .7, "collision": False, "fall": False, "task_completed": offset > 0}
            for offset in (0, 500)]
    trace = tmp_path / "source.jsonl"
    trace.write_text("\n".join(json.dumps(row) for row in rows))
    metrics = derive_metrics(trace, {"scenario": scenario.model_dump(mode="json"), "policy": {"checkpoint_digest": "sha256:test"}})
    # Clearly synthetic test media, never robot execution evidence.
    video = tmp_path / "fixture-not-a-robot.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=orange:s=64x64:r=10:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(video)], check=True, timeout=20)
    files = {"simulation.mp4": video.read_bytes(), "telemetry.jsonl": trace.read_bytes(),
             "recipe.json": json.dumps(scenario.execution_recipe).encode()}
    result = {"metrics": metrics.model_dump(mode="json"),
        "artifacts": {name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()} for name, content in files.items()},
        "artifact_urls": {name: "https://worker.test/" + name + "?signed=yes" for name in files}}
    return scenario, Trial(trial_id="trl_evidence", scenario_id=scenario.scenario_id, metrics=metrics), files, result


@pytest.mark.asyncio
async def test_evidence_retention_verifies_and_replaces_expiring_urls(tmp_path):
    scenario, trial, files, result = evidence_fixture(tmp_path)
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, content=files[request.url.path.lstrip("/")])
    settings = Settings(_env_file=None, ghost_artifact_root=tmp_path / "retained",
                        isaac_job_endpoint="https://worker.test/", gr00t_checkpoint_digest="sha256:test")
    report = await EvidenceRepository(settings, httpx.MockTransport(handler)).capture(trial, scenario, result)
    assert report["status"] == "integrity_and_metric_checks_passed"
    assert report["video_decoded"] is True
    assert trial.metrics.trace_url == "/generated/trials/trl_evidence/telemetry.jsonl"
    saved = (settings.ghost_artifact_root / "trials/trl_evidence/result.json").read_text()
    assert "signed=yes" not in saved
    assert "https://worker" not in saved


@pytest.mark.asyncio
async def test_retention_rejects_untrusted_origin_and_tampered_content(tmp_path):
    scenario, trial, files, result = evidence_fixture(tmp_path)
    settings = Settings(_env_file=None, ghost_artifact_root=tmp_path / "retained",
                        isaac_job_endpoint="https://worker.test/", gr00t_checkpoint_digest="sha256:test")
    result["artifact_urls"]["simulation.mp4"] = "https://attacker.test/steal"
    with pytest.raises(ValueError, match="origin"):
        await EvidenceRepository(settings).capture(trial, scenario, result)
    settings.ghost_artifact_root = tmp_path / "second"
    result["artifact_urls"]["simulation.mp4"] = "https://worker.test/video"
    with pytest.raises(ValueError, match="integrity"):
        await EvidenceRepository(settings, httpx.MockTransport(lambda request: httpx.Response(200, content=b"tampered"))).capture(trial, scenario, result)


def test_optional_s3_replica_is_private_and_content_addressed(tmp_path):
    calls = []
    class FakeS3:
        def put_object(self, **kwargs):
            assert "ACL" not in kwargs
            assert kwargs["ServerSideEncryption"] == "AES256"
            calls.append((kwargs["Key"], kwargs["Body"].read()))
    path = tmp_path / "evidence.json"
    path.write_text('{"record":true}')
    settings = Settings(_env_file=None, ghost_artifact_bucket="private-evidence")
    replica = EvidenceRepository(settings, s3=FakeS3()).replicate(path)
    assert replica["key"].startswith("sha256/")
    assert calls[0][1] == path.read_bytes()
