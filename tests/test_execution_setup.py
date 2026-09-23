import json
import stat

import pytest
from dotenv import dotenv_values

from ghost_trials.execution_setup import inspect_checkpoint, prepare


def test_prepare_preserves_tokens_and_existing_live_configuration(tmp_path):
    root=tmp_path / "project"
    (root / "deployment").mkdir(parents=True)
    (root / "deployment/production.env.example").write_text("ISAAC_JOB_TOKEN=\nISAAC_WORKER_TOKEN=\nNEBIUS_API_KEY=\n")
    live=root / ".env"
    live.write_text("GHOST_MODE=local\n")
    output=root / "deployment/private"
    report=prepare(root,output)
    credentials=(output / "credentials.json").read_text()
    public_key=(output / "gpu_ed25519.pub").read_text()
    prepare(root,output)
    assert (output / "credentials.json").read_text()==credentials
    assert (output / "gpu_ed25519.pub").read_text()==public_key
    assert live.read_text()=="GHOST_MODE=local\n"
    worker=dotenv_values(output / "worker.env")
    production=dotenv_values(output / "production.env")
    assert worker["ISAAC_WORKER_TOKEN"]==production["ISAAC_JOB_TOKEN"]
    assert worker["ISAAC_WORKER_REQUIRE_GPU"]=="true"
    assert len(worker["ISAAC_WORKER_TOKEN"])>=48
    assert report["provider_credentials_created"] is False
    for name in ["credentials.json","worker.env","production.env","gpu_ed25519"]:
        assert stat.S_IMODE((output / name).stat().st_mode)==0o600
    assert stat.S_IMODE(output.stat().st_mode)==0o700


def checkpoint_fixture(root,tag="unitree_g1_sonic"):
    root.mkdir()
    (root / "config.json").write_text('{"model_type":"Gr00tN1d7"}')
    processor={"processor_kwargs":{"modality_configs":{tag:{"action":{"modality_keys":["motion_token","left_hand_joints","right_hand_joints"]}}}}}
    (root / "processor_config.json").write_text(json.dumps(processor))
    (root / "statistics.json").write_text(json.dumps({tag:{"action":{"mean":[0]}}}))
    # Tiny structural test fixture, not trained model weights.
    header=json.dumps({"fixture":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}).encode()
    (root / "model.safetensors").write_bytes(len(header).to_bytes(8,"little")+header+b"\0"*4)


def test_checkpoint_validation_and_content_digest(tmp_path):
    a,b=tmp_path / "a",tmp_path / "b"
    checkpoint_fixture(a)
    checkpoint_fixture(b)
    report=inspect_checkpoint(a)
    assert report["status"]=="static_checks_passed"
    assert report["gpu_inference_validated"] is False
    assert report["checkpoint_digest"]==inspect_checkpoint(b)["checkpoint_digest"]
    with pytest.raises(ValueError, match="does not match"):
        inspect_checkpoint(a, expected_digest="sha256:wrong")
    assert inspect_checkpoint(a, expected_digest=report["checkpoint_digest"])["status"] == "static_checks_passed"
    (b / "config.json").write_text('{"model_type":"changed"}')
    assert report["checkpoint_digest"]!=inspect_checkpoint(b)["checkpoint_digest"]


def test_checkpoint_rejects_wrong_embodiment_missing_shards_and_truncation(tmp_path):
    wrong=tmp_path / "base"
    checkpoint_fixture(wrong,"real_g1")
    with pytest.raises(ValueError,match="does not support"):
        inspect_checkpoint(wrong)
    correct=tmp_path / "sonic"
    checkpoint_fixture(correct)
    (correct / "model.safetensors.index.json").write_text(json.dumps({"weight_map":{"weight":"missing.safetensors"}}))
    with pytest.raises(ValueError,match="Missing or empty"):
        inspect_checkpoint(correct)
    (correct / "model.safetensors.index.json").write_text(json.dumps({"weight_map":{"weight":"../outside.safetensors"}}))
    with pytest.raises(ValueError,match="unsafe path"):
        inspect_checkpoint(correct)
