import json
import hashlib
import asyncio
import subprocess
import sys

import pytest

from ghost_trials.cpu_robot import BACKEND, available_policies, controller, execute, recipe, validate_recipe
from ghost_trials.cpu_evidence import verify_cpu_bundle
from ghost_trials.hunt import default_space
from ghost_trials.hunt_runtime import HuntService
from ghost_trials.durable import DurableStore
from ghost_trials.config import Settings


def test_cpu_physics_loads_robot_and_measures_success_and_failure():
    easy, easy_rows, version = execute(recipe(42, {"object_mass_kg": .15, "surface_friction": .3}), "gantry-push-v1")
    hard, hard_rows, _ = execute(recipe(42, {"object_mass_kg": 1.0, "surface_friction": 1.2}), "gantry-push-v1")
    assert version and easy["robot_model"] == "ghost-gantry-xy-v1"
    assert easy["task_completed"] is True and hard["task_completed"] is False
    assert easy["object_final_x_m"] > hard["object_final_x_m"] + .2
    assert easy["max_contact_force_n"] > 0 and hard["max_contact_force_n"] > 0
    assert easy["simulation_duration_s"] == hard["simulation_duration_s"] == 3.0
    assert easy["trace_samples"] == len(easy_rows) and len(hard_rows) == len(easy_rows)
    assert easy_rows[0]["joint_positions_m"] != easy_rows[-1]["joint_positions_m"]


def test_cpu_controls_and_controller_identity_are_bounded():
    space = default_space("object_positioning", BACKEND)
    assert {d.name for d in space.dimensions} == {"object_mass_kg", "surface_friction", "object_position_x_m", "controller_delay_s"}
    with pytest.raises(ValueError, match="Unsupported"):
        recipe(1, {"gripper_force_n": 10})
    with pytest.raises(ValueError, match="outside executable bounds"):
        recipe(1, {"object_mass_kg": 500})
    with pytest.raises(ValueError, match="identity"):
        validate_recipe({**recipe(1), "seed": 2}, 1)
    assert controller("gantry-push-v1").digest != controller("gantry-push-v2").digest


def test_lightweight_cpu_neural_checkpoint_executes_without_policy_substitution(tmp_path, monkeypatch):
    assert "gantry-mlp-example" in available_policies()
    neural, rows, _ = execute(recipe(7), "gantry-mlp-example")
    classical, _, _ = execute(recipe(7), "gantry-push-v1")
    assert neural["policy_id"] == "gantry-mlp-example" and neural["policy_version"] == "1"
    assert neural["policy_digest"] == controller("gantry-mlp-example").digest
    assert neural["object_final_x_m"] != classical["object_final_x_m"]
    assert len(rows) > 100 and rows[-1]["controller_target_x_m"] != rows[0]["controller_target_x_m"]
    monkeypatch.setenv("GHOST_CPU_POLICY_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unsupported CPU policy"):
        controller("gantry-mlp-example")


def test_cpu_full_api_hunt_replay_regression_and_evidence(tmp_path):
    result = subprocess.run([sys.executable, "-m", "scripts.cpu_smoke", "--output", str(tmp_path),
                             "--strategy", "grid", "--trials", "9"],
                            capture_output=True, text=True, timeout=90, check=True)
    report = json.loads(result.stdout[result.stdout.index("{\n"):])
    assert report["status"] == "complete" and report["trials_executed"] == 9
    assert report["failures_discovered"] >= 1
    assert report["evidence_verification"] == "cpu_trace_metrics_verified"
    assert report["replay_status"] == "done"
    assert report["baseline_final_x_m"] == report["replay_final_x_m"]
    assert report["regression_outcome"] in {"fixed_on_case", "still_failing"}
    bundle = tmp_path / "artifacts" / "trials" / report["artifact_directory"].split("/")[-1]
    summary = json.loads((bundle / "summary.json").read_text())
    assert verify_cpu_bundle(bundle, summary["policy_digest"])["status"] == "cpu_trace_metrics_verified"
    retained = DurableStore(tmp_path / "state.sqlite3")
    asyncio.run(retained.load())
    service = HuntService(retained, None, Settings(_env_file=None, ghost_artifact_root=tmp_path / "artifacts"), None, None)
    assert service.case(report["case_id"]).evidence_verification["status"] == "cpu_trace_metrics_verified"
    trace = bundle / "telemetry.jsonl"
    trace.write_text(trace.read_text().replace("object_position_m", "faked_position_m", 1))
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_cpu_bundle(bundle, summary["policy_digest"])
    assert service.case(report["case_id"]).evidence_verification["status"] == "invalid_retained_evidence"
    from ghost_trials.app import regression_view
    assert regression_view(service.case(report["case_id"]), retained.trials[report["candidate_trial_id"]])[
        "outcome"] == "incompatible_or_unverified"
    trace.write_text(trace.read_text().replace("faked_position_m", "object_position_m", 1))
    summary["task_completed"] = not summary["task_completed"]
    summary_bytes = json.dumps(summary).encode()
    (bundle / "summary.json").write_bytes(summary_bytes)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["summary.json"] = {"bytes": len(summary_bytes), "sha256": hashlib.sha256(summary_bytes).hexdigest()}
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="outcome"):
        verify_cpu_bundle(bundle, summary["policy_digest"])


def test_neural_policy_runs_through_cpu_hunt_worker(tmp_path):
    result = subprocess.run([sys.executable, "-m", "scripts.cpu_smoke", "--output", str(tmp_path),
                             "--policy-id", "gantry-mlp-example", "--strategy", "grid", "--trials", "3"],
                            capture_output=True, text=True, timeout=90, check=True)
    report = json.loads(result.stdout[result.stdout.index("{\n"):])
    assert report["status"] == "complete" and report["failures_discovered"] >= 1
    assert report["evidence_verification"] == "cpu_trace_metrics_verified"
    assert report["baseline_policy_digest"] == controller("gantry-mlp-example").digest
    assert report["candidate_policy_digest"] == controller("gantry-push-v2").digest
