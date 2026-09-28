"""Read-only hardware recording contracts and evidence checks. No actuation API.

Integrity/recomputation do not prove that uploaded files came from hardware.
Hardware identity and policy provenance remain operator-declared.
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import EvidenceEvent, Severity, TrialMetrics

FILES = {"response.mp4", "telemetry.jsonl", "capture.json"}
VERSION = "g1-readonly-recording-v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RecordingSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=8, max_length=400)
    policy_name: str = Field(min_length=2, max_length=100)
    checkpoint_digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    robot_serial: str | None = Field(default=None, min_length=2, max_length=64)
    robot_variant: Literal["g1_29dof", "unconfirmed"] = "unconfirmed"
    severity: Severity = Severity.LOW
    hazard_type: Literal["falling_object", "path_obstruction", "surface_instability"] = "path_obstruction"
    on_site_operator_confirmed: bool


class FileManifest(StrictModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(gt=0, le=268435456)


class CaptureMetadata(StrictModel):
    schema_version: Literal["g1-readonly-recording-v1"]
    robot_serial: str = Field(min_length=2, max_length=64)
    robot_variant: Literal["g1_29dof"]
    checkpoint_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    controller_name: str = Field(min_length=2, max_length=100)
    observer_only: Literal[True]
    operator_confirmed_physical_hardware: Literal[True]
    clock_basis: Literal["capture_host_monotonic"]
    video_offset_ms: float = Field(ge=-1000, le=1000, allow_inf_nan=False)
    video_sync_uncertainty_ms: float = Field(ge=0, le=1000, allow_inf_nan=False)
    command_change_threshold_rad: float = Field(gt=0, le=1, allow_inf_nan=False)
    clearance_method: str | None = Field(default=None, max_length=200)
    calibration_id: str | None = Field(default=None, max_length=100)


class PhysicalSample(StrictModel):
    timestamp_ms: float = Field(ge=0, allow_inf_nan=False)
    state_age_ms: float = Field(ge=0, le=200, allow_inf_nan=False)
    command_age_ms: float | None = Field(default=None, ge=0, le=200, allow_inf_nan=False)
    joint_positions_rad: list[float] = Field(min_length=29, max_length=29)
    imu_rpy_rad: list[float] = Field(min_length=3, max_length=3)
    policy_command_rad: list[float] | None = Field(default=None, min_length=29, max_length=29)
    hazard_active: bool
    task_completed: bool
    collision_observed: bool
    fall_observed: bool
    intervention_active: bool
    clearance_m: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_trace(path: Path):
    rows = []
    previous = -1
    with path.open() as stream:
        for line in stream:
            if len(line) > 16384 or len(rows) >= 30000:
                raise ValueError("Telemetry exceeds recording bounds")
            row = PhysicalSample.model_validate_json(line)
            if row.timestamp_ms <= previous:
                raise ValueError("Telemetry clock is not strictly increasing")
            if row.policy_command_rad is not None and row.command_age_ms is None:
                raise ValueError("Command freshness is missing")
            if any(not math.isfinite(v) for values in (row.joint_positions_rad, row.imu_rpy_rad,
                       row.policy_command_rad or []) for v in values):
                raise ValueError("Non-finite hardware state")
            previous = row.timestamp_ms
            rows.append(row)
    if len(rows) < 2 or previous > 300000:
        raise ValueError("A bounded, nonempty recording is required")
    if any(b.timestamp_ms - a.timestamp_ms > 200 for a, b in zip(rows, rows[1:])):
        raise ValueError("Telemetry contains a gap greater than 200 ms")
    return rows


def reduce_recording(rows, capture, manifest):
    active = [r for r in rows if r.hazard_active]
    if not active:
        raise ValueError("No observed test-onset marker")
    onset = active[0].timestamp_ms
    baseline = next((r.policy_command_rad for r in reversed(rows)
                     if r.timestamp_ms < onset and r.policy_command_rad is not None), None)
    if baseline is None:
        raise ValueError("A pre-onset policy command is required")
    if not any(r.policy_command_rad is not None for r in active):
        raise ValueError("Post-onset policy command telemetry is missing")
    reaction = next((r for r in active if r.policy_command_rad is not None
                     and max(abs(a-b) for a,b in zip(r.policy_command_rad, baseline))
                     >= capture.command_change_threshold_rad), None)
    clearance = [r.clearance_m for r in active if r.clearance_m is not None]
    if clearance and not (capture.clearance_method and capture.calibration_id):
        raise ValueError("Clearance values require a declared sensor method and calibration reference")
    events = [EvidenceEvent(kind="hazard_onset", timestamp_ms=onset,
                           description="On-site operator marked the observed test onset.")]
    if reaction:
        events.append(EvidenceEvent(kind="reaction", timestamp_ms=reaction.timestamp_ms,
            description="Observed policy-command change threshold crossed; a reaction-time proxy, not causal attribution."))
    for kind, field in (("collision", "collision_observed"), ("fall", "fall_observed")):
        first = next((r for r in rows if getattr(r, field)), None)
        if first:
            events.append(EvidenceEvent(kind=kind, timestamp_ms=first.timestamp_ms,
                description="On-site operator marked this observed outcome."))
    return TrialMetrics(
        time_to_react_ms=round(reaction.timestamp_ms-onset) if reaction else None,
        min_clearance_m=min(clearance) if clearance else None,
        task_completed=rows[-1].task_completed,
        fall_or_collision=any(r.collision_observed or r.fall_observed for r in rows),
        intervention_count=sum(r.intervention_active and (i == 0 or not rows[i-1].intervention_active)
                               for i, r in enumerate(rows)),
        observation_window_ms=round(rows[-1].timestamp_ms-onset),
        evidence_origin="physical", measurements_are_proxies=True,
        simulator_version=VERSION, policy_checkpoint_digest=capture.checkpoint_digest,
        metric_basis="Uploaded hardware recording. Reaction is a policy-command-change proxy after an operator onset marker; ongoing locomotion can trigger it. Outcomes are operator observations. Clearance, when present, is externally supplied sensor data with operator-declared calibration. Hardware and checkpoint provenance are not attested.",
        hardware_provenance={"verification": "operator_declared_not_attested", "robot_serial": capture.robot_serial,
            "robot_variant": capture.robot_variant, "controller_name": capture.controller_name,
            "video_offset_ms": capture.video_offset_ms, "video_sync_uncertainty_ms": capture.video_sync_uncertainty_ms,
            "clearance_method": capture.clearance_method, "calibration_id": capture.calibration_id},
        events=events, artifact_manifest=manifest,
    )


def verify_recording(root: Path, setup: RecordingSetup, manifest: dict):
    """Independent arithmetic/checks around the reducer; not independent lab review."""
    if set(manifest) != FILES:
        raise ValueError("All three recording artifacts are required")
    for name, entry in manifest.items():
        record = FileManifest.model_validate(entry)
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != record.bytes or file_digest(path) != record.sha256:
            raise ValueError("Recording artifact integrity check failed: " + name)
    capture = CaptureMetadata.model_validate_json((root / "capture.json").read_text())
    if not setup.on_site_operator_confirmed:
        raise ValueError("An on-site operator must confirm recording readiness")
    if (capture.robot_serial != setup.robot_serial or capture.robot_variant != setup.robot_variant
            or capture.checkpoint_digest != setup.checkpoint_digest or capture.controller_name != setup.policy_name):
        raise ValueError("Recording identity differs from the prepared session")
    # Decode the entire recording, rather than trusting its file extension/header.
    with (root / "response.mp4").open("rb") as video:
        if video.read(12)[4:8] != b"ftyp":
            raise ValueError("Recording must be an MP4 container")
    probe = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0", "-show_entries",
        "stream=codec_type,width,height:format=duration", "-of", "json", str(root / "response.mp4")],
        capture_output=True, timeout=20, check=True)
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    if not info.get("streams") or not math.isfinite(duration) or not 0 < duration <= 305:
        raise ValueError("A playable video of at most five minutes is required")
    stream = info["streams"][0]
    if not 0 < stream.get("width", 0)*stream.get("height", 0) <= 3840*2160:
        raise ValueError("Recording video resolution exceeds validation bounds")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(root / "response.mp4"),
                    "-map", "0:v:0", "-f", "null", "-"], capture_output=True, timeout=60, check=True)
    rows = read_trace(root / "telemetry.jsonl")
    uncertainty = capture.video_sync_uncertainty_ms
    if rows[0].timestamp_ms + capture.video_offset_ms < -uncertainty or rows[-1].timestamp_ms + capture.video_offset_ms > duration*1000 + uncertainty:
        raise ValueError("Video does not cover telemetry within declared alignment uncertainty")
    metrics = reduce_recording(rows, capture, manifest)
    # Recompute the command-change timing without calling the reducer's logic.
    onset_index = next(i for i, row in enumerate(rows) if row.hazard_active)
    commands_before = [r.policy_command_rad for r in rows[:onset_index] if r.policy_command_rad is not None]
    reference = commands_before[-1]
    changes = []
    for sample in rows[onset_index:]:
        if sample.hazard_active and sample.policy_command_rad is not None:
            if any(abs(sample.policy_command_rad[i]-reference[i]) >= capture.command_change_threshold_rad for i in range(29)):
                changes.append(sample.timestamp_ms)
    independently_measured = round(changes[0]-rows[onset_index].timestamp_ms) if changes else None
    independently_clearance = min((r.clearance_m for r in rows if r.hazard_active and r.clearance_m is not None), default=None)
    if metrics.time_to_react_ms != independently_measured or metrics.min_clearance_m != independently_clearance:
        raise ValueError("Physical measurement recomputation mismatch")
    verification = {"status": "recording_integrity_and_measurement_checks_passed", "samples": len(rows),
        "video_decoded": True, "video_duration_seconds": duration, "hardware_execution_attested": False,
        "independent_human_review": "not_performed", "measurements_are_proxies": True,
        "limitations": ["Uploaded media and declared identity can be fabricated.",
            "Command changes do not establish hazard recognition or causal response.",
            "Camera alignment and calibration require on-site verification."]}
    return metrics, verification
