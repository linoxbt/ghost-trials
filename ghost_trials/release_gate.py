"""Fail-closed offline promotion gate, not a safety certificate or GPU attestation."""
import argparse
import asyncio
import hashlib
import json
import subprocess
from pathlib import Path

from .config import get_settings
from .durable import DurableStore
from .independent_validation import verify_bundle
from .review_audit import ReviewLabel, audit_reviews


def decode_video(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing video")
    # Local inputs only; no network fetch, stdin or shell interpolation.
    run = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
        "-i", str(path.resolve()), "-map", "0:v:0", "-progress", "pipe:1", "-f", "null", "-"],
        capture_output=True, timeout=120)
    if run.returncode:
        raise ValueError("Video decode failed")
    frames = [int(line.partition(b"=")[2]) for line in run.stdout.splitlines() if line.startswith(b"frame=")]
    if not frames or max(frames) < 1:
        raise ValueError("Video decode produced no frames")


def release_report(trials, scenarios, root, expected_checkpoint, reviews, min_trials=6):
    failures, accepted = [], []
    for trial in trials:
        if trial.status != "done" or not trial.metrics or trial.metrics.evidence_origin != "simulator":
            continue
        scenario = scenarios[trial.scenario_id]
        try:
            verify_bundle(root / "trials" / trial.trial_id, expected_checkpoint)
            if trial.metrics.policy_checkpoint_digest != expected_checkpoint:
                raise ValueError("Trial checkpoint mismatch")
            if not trial.tier_used or "nemotron" not in trial.tier_used.lower():
                raise ValueError("Missing Nemotron finding")
            cosmos = root / scenario.scenario_id / "cosmos.mp4"
            declared = (cosmos.parent / "cosmos.sha256").read_text().split()[0]
            with cosmos.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != declared:
                    raise ValueError("Cosmos recording integrity mismatch")
            decode_video(cosmos)
            decode_video(root / "trials" / trial.trial_id / "simulation.mp4")
            accepted.append(trial)
        except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
            failures.append({"trial_id": trial.trial_id, "issue": str(exc)})
    if len(accepted) < min_trials:
        failures.append({"issue": f"Need at least {min_trials} complete real-evidence trials"})
    hazard_seeds = {}
    for trial in accepted:
        scenario = scenarios[trial.scenario_id]
        hazard_seeds.setdefault(scenario.structured_description.hazard_type, set()).add(scenario.seed)
    for hazard in ("falling_object", "path_obstruction", "surface_instability"):
        if len(hazard_seeds.get(hazard, set())) < 2:
            failures.append({"issue": f"Need two distinct seeds for {hazard}"})
    reference = [review for review in reviews if review.trial_id in {trial.trial_id for trial in accepted}]
    review_report = audit_reviews(accepted, reference)
    if review_report["unreviewed_trials"] or not reference:
        failures.append({"issue": "Independent reference labels required for every accepted trial"})
    if review_report["disagreements"]:
        failures.append({"issue": "Reviewer disagreements require resolution before promotion"})
    return {"status": "blocked" if failures else "evidence_gates_passed", "real_trials_checked": len(accepted),
            "failures": failures, "review": review_report, "certification": False,
            "gpu_execution_attested": False, "reviewer_independence_verified": False,
            "limitations": ["This gate does not authenticate the independence of supplied reviewers or provenance of model execution.",
                "Measurement proxies and confidence calibration require expert validation.",
                "Baseline comparisons and real-world transfer are outside this minimum promotion gate."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--min-trials", type=int, default=6)
    args = parser.parse_args()
    if args.min_trials < 6:
        parser.error("The minimum gate is six real trials, not synthetic examples")
    settings = get_settings()
    store = DurableStore(settings.ghost_data_path)
    asyncio.run(store.load())
    reviews = [ReviewLabel.model_validate(row) for row in json.loads(args.reviews.read_text())] if args.reviews else []
    report = release_report(list(store.trials.values()), store.scenarios, settings.ghost_artifact_root,
                            settings.gr00t_checkpoint_digest, reviews, args.min_trials)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "evidence_gates_passed" else 1)


if __name__ == "__main__":
    main()
