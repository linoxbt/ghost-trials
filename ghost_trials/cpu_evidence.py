"""Retain and independently recompute headless CPU MuJoCo trajectory evidence."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import shutil
from pathlib import Path

from .cpu_robot import ROBOT_ID, controller, controller_source_digest, initial_block_y, validate_recipe


ARTIFACTS = ("telemetry.jsonl", "recipe.json", "summary.json", "trajectory.svg")


def _digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def trajectory_svg(rows: list[dict]) -> bytes:
    def xcoord(x):
        return round(35 + x * 680, 2)
    def ycoord(y):
        return round(120 - y * 250, 2)
    points = " ".join(f"{xcoord(r['object_position_m'][0])},{ycoord(r['object_position_m'][1])}" for r in rows)
    arm = " ".join(f"{xcoord(r['pusher_position_m'][0])},{ycoord(r['pusher_position_m'][1])}" for r in rows)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 250" role="img" aria-label="State-derived MuJoCo trajectory; not camera footage">'
            '<rect width="700" height="250" fill="#151b25"/><rect x="470" y="95" width="150" height="50" fill="#3c7159" opacity=".5"/>'
            f'<polyline points="{points}" fill="none" stroke="#ff8054" stroke-width="4"/>'
            f'<polyline points="{arm}" fill="none" stroke="#77c9ff" stroke-width="2"/>'
            '<text x="25" y="225" fill="white" font-size="13">Orange: block center · blue: gantry pusher · MuJoCo state trajectory</text></svg>').encode()


def verify_cpu_bundle(root: Path, expected_digest: str) -> dict:
    root = root.resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text())
    if set(manifest) != set(ARTIFACTS):
        raise ValueError("CPU evidence manifest is incomplete")
    for name, record in manifest.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or _digest(path.read_bytes()) != record:
            raise ValueError(f"CPU evidence hash mismatch: {name}")
    config = json.loads((root / "recipe.json").read_text())
    validate_recipe(config, config["seed"])
    summary = json.loads((root / "summary.json").read_text())
    deployed = controller(summary["policy_id"])
    if (summary["robot_model"] != ROBOT_ID or summary["simulator"] != "MuJoCo"
            or not summary.get("simulator_version") or summary["policy_version"] != deployed.version
            or summary["policy_digest"] != expected_digest or deployed.digest != expected_digest
            or summary.get("controller_source_digest") != controller_source_digest()):
        raise ValueError("Controller identity mismatch")
    rows = [json.loads(line) for line in (root / "telemetry.jsonl").read_text().splitlines() if line]
    if len(rows) != summary["trace_samples"] or len(rows) < 2 or len(rows) > 2000:
        raise ValueError("Invalid CPU trajectory sample count")
    previous = -1.0
    for row in rows:
        t = row["timestamp_ms"]
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= previous:
            raise ValueError("CPU trajectory timestamps are not increasing")
        previous = t
        for field in ("joint_positions_m", "joint_velocities_m_s", "object_position_m", "pusher_position_m"):
            if not isinstance(row[field], list) or not row[field] or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in row[field]):
                raise ValueError(f"Invalid CPU trajectory field {field}")
    initial = rows[0]["object_position_m"][0]
    final = rows[-1]["object_position_m"][0]
    if abs(initial - config["object_position_x_m"]) > .002:
        raise ValueError("Initial block pose differs from recipe")
    if abs(rows[0]["object_position_m"][1] - initial_block_y(config["seed"])) > .002:
        raise ValueError("Seeded initial block pose differs from telemetry")
    if abs(final - summary["object_final_x_m"]) > .000002:
        raise ValueError("Final block position differs from telemetry")
    recomputed = 0.64 <= final <= 0.86 and abs(rows[-1]["object_position_m"][1]) <= 0.12
    if recomputed is not summary["task_completed"] or abs(rows[-1]["timestamp_ms"] / 1000 - summary["simulation_duration_s"]) > .001:
        raise ValueError("CPU task outcome or duration differs from telemetry")
    if abs((final - config["object_position_x_m"]) - summary["object_displacement_m"]) > .000002:
        raise ValueError("CPU object displacement differs from telemetry")
    if abs(abs(final - .75) - summary["object_target_error_m"]) > .000002:
        raise ValueError("CPU target error differs from telemetry")
    for field in ("max_contact_force_n", "max_joint_tracking_error_m", "max_block_tilt_deg",
                  "controller_execution_time_ms", "wall_duration_s"):
        value = summary[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid CPU metric {field}")
    return {"status": "cpu_trace_metrics_verified", "verified_artifacts": len(manifest),
            "samples": len(rows), "checkpoint_digest": expected_digest,
            "task_completed_recomputed": recomputed, "video_decoded": False,
            "independent_human_review": "not_performed", "gpu_execution_attested": False,
            "limitations": ["Independent trace recomputation and hashes do not prove trusted execution or real-world transfer.",
                            "Trajectory SVG is derived from state samples; no camera footage was captured."]}


class CpuEvidenceRepository:
    def __init__(self, settings):
        self.root = settings.ghost_artifact_root

    async def capture(self, trial, scenario, result):
        if not result or not trial.metrics or not trial.metrics.robot_metrics:
            raise ValueError("CPU execution evidence is missing")
        directory = self.root / "trials" / trial.trial_id
        directory.mkdir(parents=True, exist_ok=False)
        try:
            return await asyncio.to_thread(self._write_bundle, directory, trial, scenario, result)
        except BaseException:
            # A partial bundle is never evidence and would block a later capture for this trial.
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def _write_bundle(self, directory, trial, scenario, result):
        payloads = {
            "telemetry.jsonl": ("\n".join(json.dumps(row, sort_keys=True) for row in result["trace"]) + "\n").encode(),
            "recipe.json": json.dumps(result["recipe"], sort_keys=True).encode(),
            "summary.json": json.dumps(result["summary"], sort_keys=True).encode(),
            "trajectory.svg": trajectory_svg(result["trace"]),
        }
        manifest = {name: _digest(payload) for name, payload in payloads.items()}
        for name, payload in payloads.items():
            (directory / name).write_bytes(payload)
        (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        (directory / "scenario.json").write_text(scenario.model_dump_json())
        verification = verify_cpu_bundle(directory, trial.metrics.policy_checkpoint_digest)
        (directory / "verification.json").write_text(json.dumps(verification, sort_keys=True))
        trial.metrics.artifact_manifest = manifest
        trial.metrics.trace_url = f"/generated/trials/{trial.trial_id}/telemetry.jsonl"
        trial.metrics.trajectory_url = f"/generated/trials/{trial.trial_id}/trajectory.svg"
        return verification
