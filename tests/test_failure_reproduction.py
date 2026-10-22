from ghost_trials.hunt import (GhostCase, TrialCandidate, empirical_boundary,
                               reproduction_result, compare_case_regression, failure_families)
from ghost_trials.models import Scenario, StructuredDescription, Trial, TrialMetrics, TrialStatus
from test_hunt import hunt


def checked_trial(trial_id, failed):
    metrics = TrialMetrics(time_to_react_ms=None, min_clearance_m=None,
                           task_completed=not failed, fall_or_collision=failed, evidence_origin="simulator",
                           simulator_version="mujoco-test", policy_checkpoint_digest="sha256:test",
                           simulation_video_url="/video.mp4", trace_url="/trace.jsonl", artifact_manifest={"video": "abc"})
    return Trial(trial_id=trial_id, scenario_id="s1", status=TrialStatus.DONE, metrics=metrics,
                 evidence_verification={"status": "integrity_and_metric_checks_passed", "video_decoded": True,
                                        "checkpoint_digest": "sha256:test"})


def test_reproduction_honestly_reports_flaky_failure():
    case = GhostCase(case_id="case1", hunt_id="hunt1", organization_id="org_a", baseline_trial_id="base",
                     scenario_id="s1", execution_recipe={"version": "v1"}, seed=3, environment="warehouse",
                     policy=hunt().policy, simulator_version="mujoco-test", rubric_version="warehouse-evaluation-v3",
                     measured_metrics={}, evidence_verification={}, artifact_manifest={},
                     recording_url="/video.mp4", telemetry_url="/trace.jsonl")
    result = reproduction_result(case, [checked_trial("t1", True), checked_trial("t2", False)])
    assert result.status == "flaky" and result.failures == 1 and result.attempts == ["t1", "t2"]
    assert reproduction_result(case, [checked_trial("single", True)]).status == "incomplete"
    assert reproduction_result(case, [checked_trial("t1", True), checked_trial("t2", True)]).status == "reproducible"


def test_boundary_requires_observed_verified_conditional_pair():
    h = hunt()
    controls = {d.name: d.default for d in h.search_space.dimensions}
    pass_controls = {**controls, "friction_coefficient": .6}
    fail_controls = {**controls, "friction_coefficient": .2}
    h.candidates = [
        TrialCandidate(sequence=1, phase="boundary", controls=pass_controls, seed=5, trial_id="p",
                       outcome="pass", evidence_class="artifact_validated_simulation", simulator_version="mujoco-test"),
        TrialCandidate(sequence=2, phase="boundary", controls=fail_controls, seed=5, trial_id="f",
                       outcome="failure", evidence_class="artifact_validated_simulation", simulator_version="mujoco-test"),
    ]
    boundary = empirical_boundary(h)
    assert boundary and boundary.pass_value == .6 and boundary.fail_value == .2
    assert boundary.supporting_trial_ids == ["p", "f"]
    assert "not a universal threshold" in boundary.statement
    h.candidates[0].seed = 6
    assert empirical_boundary(h) is None
    h.candidates[0].seed = 5
    h.candidates[0].evidence_class = "synthetic_demo"
    assert empirical_boundary(h) is None


def test_regression_rejects_incompatible_or_synthetic_cohort():
    case = GhostCase(case_id="case1", hunt_id="hunt1", organization_id="org_a", baseline_trial_id="base",
                     scenario_id="s1", execution_recipe={"version": "v1"}, seed=3, environment="warehouse",
                     policy=hunt().policy, simulator_version="mujoco-test", rubric_version="warehouse-evaluation-v3",
                     measured_metrics={}, evidence_verification={}, artifact_manifest={},
                     recording_url="/video.mp4", telemetry_url="/trace.jsonl")
    scenario = Scenario(scenario_id="s1", seed=3, prompt="The floor becomes slippery", severity_tag="medium",
                        structured_description=StructuredDescription(objects=["floor"], hazard_type="surface_instability",
                            severity="medium", expected_safe_behavior="Remain upright"), execution_recipe={"version": "v1"})
    baseline = checked_trial("base", True)
    candidate = checked_trial("candidate", False)
    candidate.metrics.policy_checkpoint_digest = "sha256:new"
    changed = scenario.model_copy(deep=True)
    changed.execution_recipe = {"version": "v2"}
    result = compare_case_regression(case, baseline, candidate, scenario, changed)
    assert result.outcome == "incompatible_or_unverified"
    assert any("recipe" in warning.lower() for warning in result.comparison["warnings"])


def test_failure_families_group_only_matching_deterministic_signals():
    base = GhostCase(case_id="a", hunt_id="h", organization_id="org_a", baseline_trial_id="t",
                     scenario_id="s", execution_recipe={"kind": "falling_object"}, seed=2,
                     environment="warehouse", task="Walk aisle", hazard_type="falling_object",
                     observed_failure_mode="fall_or_collision", policy=hunt().policy,
                     simulator_version="mujoco-test", rubric_version="warehouse-evaluation-v3",
                     measured_metrics={}, evidence_verification={}, artifact_manifest={},
                     recording_url="/video.mp4", telemetry_url="/trace.jsonl")
    related = base.model_copy(update={"case_id": "b"})
    unrelated = base.model_copy(update={"case_id": "c", "observed_failure_mode": "task_noncompletion"})
    families = failure_families([base, related, unrelated])
    assert len(families) == 2
    assert any(f.case_ids == ["a", "b"] for f in families)
