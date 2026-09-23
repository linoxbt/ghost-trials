"""Fail-closed adapter from a real simulator trace to the Ghost Trials metric contract.

The configured backend command must run Isaac Lab-Arena+GR00T or GEAR-SONIC sim and
write telemetry.jsonl plus simulation.mp4 in the job output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ghost_trials.models import EvidenceEvent, TrialMetrics


class TelemetrySample(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow", allow_inf_nan=False)
    timestamp_ms: float = Field(ge=0)
    hazard_active: bool
    policy_reacted: bool
    clearance_m: float | None = Field(ge=0)
    collision: bool
    fall: bool
    intervention: bool = False
    task_completed: bool = False
    simulator_version: str | None = None
    metric_basis: str | None = None
    contact_slip_speed_m_s: float | None = Field(default=None, ge=0)
    effective_friction: float | None = Field(default=None, ge=0, le=2)
    ground_contact_count: int = Field(default=0, ge=0)


def derive_metrics(trace_path: Path, request: dict) -> TrialMetrics:
    rows = [TelemetrySample.model_validate_json(line).model_dump() for line in trace_path.read_text().splitlines() if line.strip()]
    if not rows:
        raise RuntimeError("telemetry.jsonl contains no samples")
    if any(b["timestamp_ms"] <= a["timestamp_ms"] for a, b in zip(rows, rows[1:])):
        raise RuntimeError("telemetry timestamps must be strictly increasing")
    hazard_rows = [row for row in rows if row.get("hazard_active")]
    reaction_rows = [row for row in hazard_rows if row.get("policy_reacted")]
    if not hazard_rows:
        raise RuntimeError("telemetry has no hazard_active sample; scenario was not injected")
    onset = min(float(row["timestamp_ms"]) for row in hazard_rows)
    reaction = min((float(row["timestamp_ms"]) for row in reaction_rows), default=None)
    clearances = [float(row["clearance_m"]) for row in hazard_rows if row.get("clearance_m") is not None]
    traction = request.get("scenario", {}).get("structured_description", {}).get("hazard_type") == "surface_instability"
    contact_rows = [r for r in hazard_rows if r["ground_contact_count"] > 0]
    slip = [r["contact_slip_speed_m_s"] for r in contact_rows if r["contact_slip_speed_m_s"] is not None]
    friction = [r["effective_friction"] for r in contact_rows if r["effective_friction"] is not None]
    if traction:
        from workers.isaac.hazards import compile_hazard
        coefficient = compile_hazard(request["scenario"]).friction_coefficient
        if not contact_rows or len(slip) != len(contact_rows) or len(friction) != len(contact_rows):
            raise RuntimeError("Traction trial needs measured ground contacts, slip speed, and effective friction")
        if any(abs(mu - coefficient) > 1e-6 for mu in friction):
            raise RuntimeError("Recorded friction differs from the traction recipe")
    elif not clearances:
        raise RuntimeError("telemetry contains no clearance measurements")
    checkpoint_digest = request["policy"].get("checkpoint_digest")
    events = [EvidenceEvent(kind="hazard_onset", timestamp_ms=onset, description="First hazard-active telemetry sample")]
    if reaction is not None:
        events.append(EvidenceEvent(kind="reaction", timestamp_ms=reaction, description="First observed policy-action response; not causal proof"))
    if clearances and not traction:
        closest = min((r for r in hazard_rows if r["clearance_m"] is not None), key=lambda r: r["clearance_m"])
        events.append(EvidenceEvent(kind="closest_approach", timestamp_ms=closest["timestamp_ms"], description=f"Minimum measured clearance: {closest['clearance_m']:.3f} m; see metric basis"))
    for kind in ("collision", "fall"):
        first = next((r for r in rows if r[kind]), None)
        if first:
            events.append(EvidenceEvent(kind=kind, timestamp_ms=first["timestamp_ms"], description=f"First recorded {kind}; causation not established"))
    events.append(EvidenceEvent(kind="outcome", timestamp_ms=rows[-1]["timestamp_ms"], description="Final telemetry sample"))
    return TrialMetrics(
        time_to_react_ms=round(reaction - onset) if reaction is not None else None,
        min_clearance_m=round(min(clearances), 3) if clearances and not traction else None,
        max_contact_slip_speed_m_s=max(slip) if traction else None,
        effective_friction=min(friction) if traction else None,
        task_completed=bool(rows[-1].get("task_completed", False)),
        fall_or_collision=any(bool(row.get("fall") or row.get("collision")) for row in rows),
        intervention_count=sum(bool(row["intervention"]) and (i == 0 or not rows[i - 1]["intervention"]) for i, row in enumerate(rows)),
        observation_window_ms=round(rows[-1]["timestamp_ms"] - onset),
        metric_basis=rows[0].get("metric_basis"),
        simulation_video_url="simulation.mp4",
        trace_url="telemetry.jsonl",
        simulator_version=rows[0].get("simulator_version") or "unknown",
        policy_checkpoint_digest=checkpoint_digest,
        evidence_origin="simulator",
        events=sorted(events, key=lambda event: event.timestamp_ms),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    backend = request["execution_backend"]
    if backend not in {"isaac_arena_gr00t", "gear_sonic_sim"}:
        raise ValueError("Unsupported execution backend")
    variable = "ISAAC_ARENA_COMMAND" if backend == "isaac_arena_gr00t" else "GEAR_SONIC_SIM_COMMAND"
    command_template = os.getenv(variable)
    if not command_template:
        raise RuntimeError(f"{variable} is required; no synthetic fallback is allowed")
    command = [part.format(request=str(args.request), output=str(args.output)) for part in shlex.split(command_template)]
    subprocess.run(command, check=True, cwd=os.getenv("ROBOTICS_WORKDIR") or None)
    trace_path = args.output / "telemetry.jsonl"
    video_path = args.output / "simulation.mp4"
    if not trace_path.is_file() or not video_path.is_file():
        raise RuntimeError("backend must produce telemetry.jsonl and simulation.mp4")
    with video_path.open("rb") as video:
        header = video.read(12)
    if len(header) < 12 or header[4:8] != b"ftyp":
        raise RuntimeError("simulation.mp4 is not an MP4 container")
    metrics = derive_metrics(trace_path, request)
    artifacts = {}
    for path in (trace_path, video_path, *([args.output / "recipe.json"] if (args.output / "recipe.json").is_file() else [])):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        artifacts[path.name] = {
            "sha256": digest.hexdigest(),
            "bytes": path.stat().st_size,
        }
    (args.output / "result.json").write_text(json.dumps({"metrics": metrics.model_dump(), "artifacts": artifacts}, indent=2))


if __name__ == "__main__":
    main()
