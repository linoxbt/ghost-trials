import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from ghost_trials import gpu_acceptance, provider_check
from ghost_trials.checkpoint_access import compatible_metadata, safe_prefix
from ghost_trials.config import Settings
from ghost_trials.independent_validation import verify_bundle
from workers.isaac.hazards import compile_hazard


def bundle(root):
    root.mkdir()
    rows = [{"timestamp_ms": t, "hazard_active": True, "policy_reacted": t > 3000,
             "collision": False, "fall": False, "clearance_m": None, "task_completed": t == 3500,
             "ground_contact_count": 2, "effective_friction": .2, "contact_slip_speed_m_s": .1}
            for t in (3000, 3500)]
    files = {"telemetry.jsonl": "\n".join(map(json.dumps, rows)).encode(),
             "simulation.mp4": b"\x00\x00\x00\x18ftypisom",  # Signature fixture, not a decodable video.
             "recipe.json": json.dumps(compile_hazard({"seed": 42, "severity_tag": "medium",
                 "structured_description": {"hazard_type": "surface_instability"}}).to_dict()).encode()}
    for name, content in files.items():
        (root / name).write_bytes(content)
    result = {"metrics": {"policy_checkpoint_digest": "sha256:test", "time_to_react_ms": 500,
              "min_clearance_m": None, "task_completed": True, "fall_or_collision": False,
              "observation_window_ms": 500, "intervention_count": 0,
              "max_contact_slip_speed_m_s": .1, "effective_friction": .2,
              "simulation_video_url": "https://worker/video", "trace_url": "https://worker/trace"},
              "artifacts": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
    (root / "result.json").write_text(json.dumps(result))
    return result, files


def test_independent_verifier_detects_changed_metrics_and_bytes(tmp_path):
    root = tmp_path / "bundle"
    result, _ = bundle(root)
    report = verify_bundle(root, "sha256:test")
    assert report["independent_human_review"] == "not_performed"
    assert report["gpu_execution_attested"] is False
    result["metrics"]["time_to_react_ms"] = 10
    (root / "result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="recomputation"):
        verify_bundle(root, "sha256:test")
    (root / "telemetry.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        verify_bundle(root, "sha256:test")


def test_independent_verifier_rejects_wrong_identity_and_boolean_coercion(tmp_path):
    root = tmp_path / "bundle"
    result, _ = bundle(root)
    with pytest.raises(ValueError, match="identity"):
        verify_bundle(root, "sha256:other")
    result["metrics"]["task_completed"] = 1
    (root / "result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="recomputation"):
        verify_bundle(root, "sha256:test")


def test_checkpoint_contract_rejects_base_or_controller_weights():
    processor = {"processor_kwargs": {"modality_configs": {"unitree_g1_sonic": {
        "action": {"modality_keys": ["motion_token", "left_hand_joints", "right_hand_joints"]}}}}}
    compatible_metadata({"model_type": "Gr00tN1d7"}, processor, {"unitree_g1_sonic": {"action": {}}}, "unitree_g1_sonic")
    with pytest.raises(ValueError, match="compatible"):
        compatible_metadata({"model_type": "Gr00tN1d7"}, processor, {"real_g1": {}}, "unitree_g1_sonic")
    processor["processor_kwargs"]["modality_configs"]["unitree_g1_sonic"]["action"]["modality_keys"] = ["joint_positions"]
    with pytest.raises(ValueError, match="actions"):
        compatible_metadata({"model_type": "Gr00tN1d7"}, processor, {"unitree_g1_sonic": {"action": {}}}, "unitree_g1_sonic")


@pytest.mark.parametrize("prefix", ["../private", "/absolute", "bad\\path"])
def test_checkpoint_path_safety(prefix):
    with pytest.raises(ValueError):
        safe_prefix(prefix)


@pytest.mark.asyncio
async def test_gpu_missing_configuration_never_calls_network(monkeypatch):
    monkeypatch.setattr(gpu_acceptance, "get_settings", lambda: Settings(_env_file=None))
    def unexpected(request):
        raise AssertionError("Network was not needed")
    result = await gpu_acceptance.acceptance(transport=httpx.MockTransport(unexpected))
    assert result["status"] == "blocked" and not result["gpu_trial_executed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_origin", [False, True])
async def test_gpu_acceptance_download_and_origin_guard(tmp_path, monkeypatch, foreign_origin):
    result, files = bundle(tmp_path / "source")
    settings = Settings(_env_file=None, isaac_job_endpoint="https://worker/", isaac_job_token="secret",
                            gr00t_checkpoint="/models/policy", gr00t_checkpoint_digest="sha256:test",
                            ghost_execution_backend="gear_sonic_sim")
    monkeypatch.setattr(gpu_acceptance, "get_settings", lambda: settings)
    result["artifact_urls"] = {name: f"https://{'other' if foreign_origin else 'worker'}/artifacts/{name}?signature=test" for name in files}
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/health/ready":
            return httpx.Response(200, json={"status": "ready", "backend": "gear_sonic_sim",
                "policy_checkpoint_digest": "sha256:test", "gpu_required": True, "policy_required": True})
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "isaac_test"})
        if request.url.path == "/v1/jobs/isaac_test":
            return httpx.Response(200, json={"status": "completed", "result": result})
        assert "authorization" not in request.headers
        return httpx.Response(200, content=files[request.url.path.rsplit("/", 1)[-1]])
    transport = httpx.MockTransport(handler)
    preflight = await gpu_acceptance.acceptance(transport=transport)
    assert not preflight["gpu_trial_executed"] and len(requests) == 1
    if foreign_origin:
        with pytest.raises(ValueError, match="origin"):
            await gpu_acceptance.acceptance(True, tmp_path / "out", transport=transport)
        assert not any(r.url.host == "other" for r in requests)
    else:
        report = await gpu_acceptance.acceptance(True, tmp_path / "out", transport=transport)
        assert report["validation"]["verified_artifacts"] == 3
        assert "signature" not in (tmp_path / "out/result.json").read_text()


@pytest.mark.asyncio
async def test_provider_check_catalog_only_does_not_invoke_inference(monkeypatch):
    settings = Settings(_env_file=None, nebius_api_key="test-secret")
    monkeypatch.setattr(provider_check, "get_settings", lambda: settings)
    def handler(request):
        assert request.method == "GET" and request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": settings.nebius_super_model}]})
    result = await provider_check.check(transport=httpx.MockTransport(handler))
    assert result["authenticated"] and result["inference_test"] == "not_run"
    assert "test-secret" not in json.dumps(result)


def test_checkpoint_access_pins_revision_before_weight_download(tmp_path, monkeypatch):
    huggingface_hub = pytest.importorskip("huggingface_hub")
    from ghost_trials.checkpoint_access import access
    metadata = {"config.json": {"model_type": "Gr00tN1d7"}, "statistics.json": {"unitree_g1_sonic": {"action": {}}},
                "processor_config.json": {"processor_kwargs": {"modality_configs": {"unitree_g1_sonic": {
                    "action": {"modality_keys": ["motion_token", "left_hand_joints", "right_hand_joints"]}}}}}}
    sha = "a" * 40
    calls = []
    def download(repo, filename, revision, token):
        assert revision == sha
        calls.append(filename)
        path = tmp_path / filename
        path.write_text(json.dumps(metadata[filename]))
        return str(path)
    info = SimpleNamespace(sha=sha, card_data=None,
        siblings=[SimpleNamespace(rfilename=name, size=100) for name in metadata] + [SimpleNamespace(rfilename="model.safetensors", size=1000)])
    monkeypatch.setattr(huggingface_hub, "HfApi", lambda **kw: SimpleNamespace(model_info=lambda *a, **k: info))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    assert access("test/policy")["revision"] == sha
    assert set(calls) == set(metadata)
    with pytest.raises(ValueError, match="budget"):
        access("test/policy", destination=tmp_path / "download", max_bytes=1)
    assert not (tmp_path / "download").exists()
