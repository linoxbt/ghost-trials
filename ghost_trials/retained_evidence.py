"""Recheck saved simulator artifacts before presenting a current evaluation verdict."""
from __future__ import annotations

import json
from pathlib import Path

from .evaluation import evidence_class
from .models import Scenario, Trial


def reporting_trial(trial: Trial, scenario: Scenario, artifact_root: Path) -> Trial:
    """Return a reporting copy; never overwrite the original execution record."""
    if evidence_class(trial) != "artifact_validated_simulation":
        return trial
    checked = trial.model_copy(deep=True)
    metrics = checked.metrics
    if metrics is None:
        checked.evidence_verification = {"status": "invalid_retained_evidence"}
        return checked
    try:
        root = artifact_root.resolve()
        directory = (root / "trials" / trial.trial_id).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Unsafe artifact directory")
        expected = metrics.policy_checkpoint_digest
        if trial.embodiment == "GHOST_GANTRY_XY":
            from .bundle_cache import cpu_bundle
            verification = cpu_bundle(directory, expected)
            manifest = json.loads((directory / "manifest.json").read_text())
            summary = json.loads((directory / "summary.json").read_text())
            recipe = json.loads((directory / "recipe.json").read_text())
            if (manifest != metrics.artifact_manifest or summary != metrics.robot_metrics
                    or recipe != scenario.execution_recipe):
                raise ValueError("CPU artifacts differ from saved trial or scenario")
        else:
            from .bundle_cache import worker_bundle
            verification = worker_bundle(directory, expected)
            result = json.loads((directory / "result.json").read_text())
            if result["artifacts"] != metrics.artifact_manifest:
                raise ValueError("Worker artifacts differ from saved trial")
            for key in ("time_to_react_ms", "min_clearance_m", "task_completed", "fall_or_collision",
                        "observation_window_ms", "policy_checkpoint_digest", "simulator_version"):
                if result["metrics"].get(key) != getattr(metrics, key):
                    raise ValueError(f"Worker metric differs from saved trial: {key}")
            recipe = json.loads((directory / "recipe.json").read_text())
            if any(recipe.get(key) != value for key, value in scenario.execution_recipe.items()):
                raise ValueError("Worker recipe differs from saved scenario")
            if trial.evidence_verification.get("video_decoded") is not True:
                raise ValueError("Recording was not decoded during evidence capture")
        if verification.get("status") != trial.evidence_verification.get("status"):
            raise ValueError("Current verification differs from stored result")
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, UnicodeError, OverflowError):
        checked.evidence_verification = {"status": "invalid_retained_evidence"}
    return checked
