"""Offline evidence verifier implemented separately from the worker's metric reducer.

Checks integrity and recomputes measurements. It is not independent human review,
an external certification, or proof that a simulator faithfully models reality.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def digest_file(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify_bundle(root: Path, expected_checkpoint: str):
    if not expected_checkpoint:
        raise ValueError("An independently supplied expected checkpoint digest is required")
    root = root.resolve(strict=True)
    result = json.loads((root / "result.json").read_text())
    metrics = result["metrics"]
    manifest = result["artifacts"]
    if not {"telemetry.jsonl", "simulation.mp4", "recipe.json"}.issubset(manifest):
        raise ValueError("Missing required trace, recording or physical recipe in artifact manifest")
    for name, record in manifest.items():
        if Path(name).name != name or "\\" in name or name in {".", ".."}:
            raise ValueError("Unsafe artifact path")
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != record["bytes"] or digest_file(path) != record["sha256"]:
            raise ValueError(f"Artifact integrity check failed: {name}")
    if metrics.get("policy_checkpoint_digest") != expected_checkpoint:
        raise ValueError("Checkpoint identity differs from the independently supplied digest")
    with (root / "simulation.mp4").open("rb") as stream:
        if stream.read(12)[4:8] != b"ftyp":
            raise ValueError("Recording is not an MP4 container; full decoding still requires playback validation")
    recipe = json.loads((root / "recipe.json").read_text())
    scenario_path = root / "scenario.json"
    if scenario_path.exists():
        scenario = json.loads(scenario_path.read_text())
        declared = scenario.get("execution_recipe")
        if not declared or any(recipe.get(key) != value for key, value in declared.items()):
            raise ValueError("Executed recipe differs from the requested scenario")
    rows = []
    with (root / "telemetry.jsonl").open() as stream:
        for line in stream:
            if len(line) > 1_000_000 or len(rows) >= 1_000_000:
                raise ValueError("Trace exceeds validation bounds")
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise ValueError("Empty telemetry")
    previous = -1
    active = []
    for row in rows:
        time = row.get("timestamp_ms")
        if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0 or time <= previous:
            raise ValueError("Telemetry timestamps must be finite and strictly increasing")
        previous = time
        for flag in ("hazard_active", "policy_reacted", "collision", "fall"):
            if type(row.get(flag)) is not bool:
                raise ValueError(f"Invalid telemetry boolean: {flag}")
        for flag in ("task_completed", "intervention"):
            if type(row.get(flag, False)) is not bool:
                raise ValueError(f"Invalid telemetry boolean: {flag}")
        if type(row.get("ground_contact_count", 0)) is not int or row.get("ground_contact_count", 0) < 0:
            raise ValueError("Invalid ground contact count")
        for field in ("clearance_m", "contact_slip_speed_m_s", "effective_friction"):
            value = row.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid measurement: {field}")
        if row["hazard_active"]:
            active.append(row)
    if not active:
        raise ValueError("No recorded hazard activation")
    first_response = next((row for row in active if row["policy_reacted"]), None)
    onset = active[0]["timestamp_ms"]
    gaps = [b["timestamp_ms"] - a["timestamp_ms"] for a, b in zip(rows, rows[1:])]
    tolerance = max(gaps, default=1) + 1
    if abs(onset - recipe["onset_s"] * 1000) > tolerance:
        raise ValueError("Hazard onset differs from the declared recipe")
    traction = recipe["kind"] == "surface_instability"
    clearance = [r["clearance_m"] for r in active if r.get("clearance_m") is not None]
    if not traction and not clearance:
        raise ValueError("Missing clearance measurements")
    recomputed = {
        "time_to_react_ms": round(first_response["timestamp_ms"] - onset) if first_response else None,
        "min_clearance_m": round(min(clearance), 3) if not traction else None,
        "task_completed": rows[-1].get("task_completed", False),
        "fall_or_collision": any(row["collision"] or row["fall"] for row in rows),
        "observation_window_ms": round(rows[-1]["timestamp_ms"] - onset),
        "intervention_count": sum(bool(row.get("intervention")) and (i == 0 or not rows[i-1].get("intervention")) for i, row in enumerate(rows)),
    }
    if traction:
        contacts = [r for r in active if r.get("ground_contact_count", 0) > 0]
        if not contacts or any(r.get("effective_friction") is None or r.get("contact_slip_speed_m_s") is None for r in contacts):
            raise ValueError("Missing traction contact measurements")
        if any(abs(r["effective_friction"] - recipe["friction_coefficient"]) > 1e-6 for r in contacts):
            raise ValueError("Effective friction differs from recipe")
        recomputed.update(max_contact_slip_speed_m_s=max(r["contact_slip_speed_m_s"] for r in contacts),
                          effective_friction=min(r["effective_friction"] for r in contacts))
    for name, expected in recomputed.items():
        actual = metrics.get(name)
        equal = actual == expected
        if isinstance(expected, bool):
            equal = type(actual) is bool and actual == expected
        if isinstance(expected, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
            equal = math.isfinite(actual) and math.isclose(actual, expected, abs_tol=.001)
        if not equal:
            raise ValueError(f"Reported metric does not match independent recomputation: {name}")
    return {"status": "integrity_and_metric_checks_passed", "samples": len(rows),
            "verified_artifacts": len(manifest), "checkpoint_digest": expected_checkpoint,
            "recomputed_metrics": recomputed, "independent_human_review": "not_performed",
            "gpu_execution_attested": False, "limitations": ["Verifier is a separate implementation, not an independent organization.",
            "A self-consistent bundle can be fabricated; trusted execution provenance and human review remain necessary.",
            "MP4 signature is checked; video content and timing require playback inspection."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--expected-checkpoint", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_bundle(args.bundle, args.expected_checkpoint), indent=2))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
