import pytest
from types import SimpleNamespace

from ghost_trials.adapters import ExecutionBlocked, LocalScenarioGenerator
from ghost_trials.durable import DurableStore
from ghost_trials.hunt import (Hunt, HuntObjective, HuntPlanner, HuntStatus, PolicyVersion,
                               TrialCandidate, case_from_trial, default_space, observed_outcome)
from ghost_trials.models import EvidenceEvent, Scenario, StructuredDescription, Trial, TrialMetrics, TrialStatus
from workers.isaac.hazards import compile_hazard, parameterize_hazard
from ghost_trials.hunt_runtime import HAZARD_PROMPTS, HuntService


def hunt(space=None, budget=12):
    return Hunt(hunt_id="hunt_test", organization_id="org_a", objective=HuntObjective(
        task="Walk through an aisle", hazard_type="surface_instability"),
        policy=PolicyVersion(name="g1", checkpoint="test", checkpoint_digest="sha256:test", embodiment="UNITREE_G1_SONIC"),
        search_space=space or default_space("surface_instability", "gear_sonic_sim"), max_trials=budget)


def synthetic_trial(outcome, trial_id="trl_test"):
    return Trial(trial_id=trial_id, scenario_id="scn_test", status=TrialStatus.DONE,
                 metrics=TrialMetrics(time_to_react_ms=None, min_clearance_m=None,
                                      task_completed=outcome != "failure", fall_or_collision=False,
                                      evidence_origin="synthetic"))


def test_hunt_budget_bounds_and_known_synthetic_region():
    h = hunt(budget=14)
    for _ in range(h.max_trials):
        c = HuntPlanner(h).next()
        assert c and h.search_space.validate_controls(c.controls) == c.controls
        # Fixture only: low friction is a synthetic test oracle, not robot telemetry.
        c.outcome, _ = observed_outcome(synthetic_trial("failure" if c.controls["friction_coefficient"] < .5 else "pass"),
                                         allow_synthetic_fixture=True)
        c.evidence_class = "synthetic_demo"
        h.candidates.append(c)
    assert HuntPlanner(h).next() is None
    assert any(c.outcome == "failure" for c in h.candidates)
    assert any(c.phase in {"mutate", "boundary"} for c in h.candidates)


def test_adaptive_moves_near_vulnerable_region_and_reproduces_identical_seed():
    h = hunt()
    for i in range(4):
        c = HuntPlanner(h).next()
        c.outcome = "failure" if i == 3 else "pass"
        h.candidates.append(c)
    source = h.candidates[-1]
    repeat = HuntPlanner(h).next()
    assert repeat.phase == "reproduce" and repeat.controls == source.controls and repeat.seed == source.seed
    repeat.outcome = "failure"
    h.candidates.append(repeat)
    second = HuntPlanner(h).next()
    assert second.phase == "reproduce" and second.controls == source.controls
    second.outcome = "failure"
    h.candidates.append(second)
    boundary = HuntPlanner(h).next()
    assert boundary.phase in {"boundary", "mutate"}
    assert h.search_space.validate_controls(boundary.controls)
    assert boundary.seed == source.seed


def test_cpu_failure_at_mass_ceiling_still_probes_observed_boundary():
    space = default_space("object_positioning", "mujoco_cpu")
    h = Hunt(hunt_id="hunt_cpu_edge", organization_id="org_a", objective=HuntObjective(
        task="position a block with gantry arm", environment="CPU MuJoCo tabletop",
        hazard_type="object_positioning"), policy=PolicyVersion(name="gantry-push-v1",
        checkpoint="builtin:gantry-push-v1:1", checkpoint_digest="sha256:test",
        embodiment="GHOST_GANTRY_XY"), search_space=space, max_trials=10)
    controls = {d.name: d.default for d in space.dimensions}
    controls["object_mass_kg"] = 1.0
    for sequence in range(1, 5):
        h.candidates.append(TrialCandidate(sequence=sequence, phase="explore", controls=controls.copy(),
                                           seed=7, outcome="failure" if sequence == 4 else "pass"))
    for _ in range(2):
        repeated = HuntPlanner(h).next()
        assert repeated.phase == "reproduce" and repeated.controls == controls
        repeated.outcome = "failure"
        h.candidates.append(repeated)
    probe = HuntPlanner(h).next()
    assert probe.phase == "boundary" and probe.seed == 7
    assert probe.controls["object_mass_kg"] == .05


def test_custom_supported_subspace_can_adapt_without_default_boundary_axis():
    space = default_space("surface_instability", "gear_sonic_sim")
    space.dimensions = [d for d in space.dimensions if d.name == "onset_s"]
    h = hunt(space)
    for i in range(4):
        candidate = HuntPlanner(h).next()
        candidate.outcome = "failure" if i == 3 else "pass"
        h.candidates.append(candidate)
    for _ in range(3):
        candidate = HuntPlanner(h).next()
        candidate.outcome = "failure"
        h.candidates.append(candidate)
    assert HuntPlanner(h).next().controls.keys() == {"onset_s"}


def test_provider_error_and_missing_evidence_are_not_policy_failures():
    blocked = Trial(trial_id="t1", scenario_id="s1", status=TrialStatus.BLOCKED, error="GPU unavailable")
    assert observed_outcome(blocked)[0] == "provider_error"
    assert observed_outcome(synthetic_trial("failure"))[0] == "insufficient_evidence"


def test_hunt_state_survives_sqlite_restart(tmp_path):
    store = DurableStore(tmp_path / "hunt.db")
    h = hunt()
    h.status = HuntStatus.INTERRUPTED
    h.candidates.append(TrialCandidate(sequence=1, phase="explore", controls={d.name: d.default for d in h.search_space.dimensions}, seed=4))
    store.put_domain("hunt", h.hunt_id, h.model_dump_json())
    restarted = DurableStore(tmp_path / "hunt.db")
    restored = Hunt.model_validate_json(restarted.get_domain("hunt", h.hunt_id))
    assert restored.status == HuntStatus.INTERRUPTED and restored.candidates[0].seed == 4


def test_unsupported_parameters_and_tampered_recipe_rejected():
    scenario = {"seed": 7, "severity_tag": "medium", "structured_description": {"hazard_type": "surface_instability"}}
    with pytest.raises(ValueError, match="Unsupported simulator parameters"):
        parameterize_hazard(scenario, {"robot_velocity_m_s": 2}, "gear_sonic_sim")
    with pytest.raises(ValueError, match="only"):
        default_space("surface_instability", "isaac_arena_gr00t")
    recipe = parameterize_hazard(scenario, {"friction_coefficient": .61}, "gear_sonic_sim").to_dict()
    scenario["execution_recipe"] = recipe
    assert compile_hazard(scenario).friction_coefficient == .61
    recipe["duration_s"] = 99
    with pytest.raises(ValueError, match="unsupported"):
        compile_hazard(scenario)


def test_synthetic_failure_cannot_become_verified_ghost_case():
    h = hunt()
    s = Scenario(scenario_id="scn_test", prompt="The floor becomes slippery", seed=3,
                 structured_description=StructuredDescription(objects=["floor"], hazard_type="surface_instability",
                     severity="medium", expected_safe_behavior="Remain upright"), severity_tag="medium",
                 execution_recipe={"some": "recipe"})
    with pytest.raises(ValueError, match="independently checked"):
        case_from_trial(h, synthetic_trial("failure"), s)


def test_live_hunt_rejects_missing_gpu_and_checkpoint_before_paid_generation():
    settings = SimpleNamespace(ghost_simulator_provider="isaac_http", isaac_job_endpoint=None, isaac_job_token=None,
        gr00t_checkpoint=None, gr00t_checkpoint_digest=None, cosmos_api_key=None, nvidia_api_key=None,
        cosmos_base_url=None, cosmos_api_style="nim", scenario_reasoner_api_key=None, nebius_api_key=None)
    service = HuntService(None, None, settings, None, None)
    with pytest.raises(ExecutionBlocked, match="GPU worker endpoint"):
        service.create("org_a", HuntObjective(task="walk forward 1m", environment="configured SONIC MuJoCo scene",
                          hazard_type="falling_object"), 3, "adaptive")


@pytest.mark.asyncio
@pytest.mark.parametrize("hazard_type", ["falling_object", "path_obstruction", "surface_instability"])
async def test_hunt_prompts_compile_to_the_requested_local_hazard(hazard_type):
    scenario = await LocalScenarioGenerator().generate("s1", HAZARD_PROMPTS[hazard_type], None, 5)
    assert scenario.structured_description.hazard_type == hazard_type


def test_verified_ghost_case_preserves_exact_replay_inputs():
    h = hunt(default_space("falling_object", "gear_sonic_sim"))
    h.objective.hazard_type = "falling_object"
    s = Scenario(organization_id="org_a", scenario_id="s1", prompt="A box falls from a shelf", seed=17,
                 structured_description=StructuredDescription(objects=["box"], hazard_type="falling_object",
                    severity="medium", expected_safe_behavior="Avoid the falling box"), severity_tag="medium")
    s.execution_recipe = parameterize_hazard(s.model_dump(mode="json"),
        {"obstacle_distance_m": .72, "obstacle_speed_m_s": 1.4}, "gear_sonic_sim").to_dict()
    metrics = TrialMetrics(time_to_react_ms=500, min_clearance_m=0.0, task_completed=False,
        fall_or_collision=True, evidence_origin="simulator", simulator_version="mujoco-test",
        policy_checkpoint_digest="sha256:test", simulation_video_url="/video.mp4", trace_url="/trace.jsonl",
        metric_basis="contact and measured displacement", artifact_manifest={"video": "abc"},
        events=[EvidenceEvent(kind="collision", timestamp_ms=1200, description="box contact")])
    trial = Trial(organization_id="org_a", trial_id="t1", scenario_id="s1", status=TrialStatus.DONE,
        embodiment="UNITREE_G1_SONIC", rubric_version="warehouse-evaluation-v3", metrics=metrics,
        evidence_verification={"status": "integrity_and_metric_checks_passed", "video_decoded": True,
                               "checkpoint_digest": "sha256:test"})
    case = case_from_trial(h, trial, s)
    assert case.seed == 17 and case.execution_recipe == s.execution_recipe
    assert case.policy.checkpoint_digest == "sha256:test"
    assert case.artifact_manifest == {"video": "abc"}


def cpu_hunt(budget=30, strategy="adaptive"):
    h = hunt(space=default_space("object_positioning", "mujoco_cpu"), budget=budget)
    h.strategy = strategy
    return h


def run_oracle(h, fails):
    """Drive the planner against a deterministic oracle; candidates carry validated-evidence labels."""
    while (c := HuntPlanner(h).next()) is not None:
        c.trial_id = f"trl_{c.sequence}"
        c.outcome = "failure" if fails(c.controls) else "pass"
        c.evidence_class, c.simulator_version = "artifact_validated_simulation", "MuJoCo test"
        h.candidates.append(c)
    return h


def test_boundary_reports_narrowest_observed_bracket():
    from ghost_trials.hunt import empirical_boundary
    h = run_oracle(cpu_hunt(), lambda c: c["object_mass_kg"] > 0.30)
    boundary = empirical_boundary(h)
    assert boundary and boundary.dimension == "object_mass_kg"
    assert boundary.pass_value <= 0.30 < boundary.fail_value
    # Bisection narrows the bracket well below the full mass range.
    assert boundary.fail_value - boundary.pass_value < 0.2
    reproductions = sum(c.phase == "reproduce" for c in h.candidates)
    assert reproductions <= max(2, h.max_trials // 4)
    assert not any(c.phase == "reproduce" and any(b.phase == "boundary" and b.controls == c.controls for b in h.candidates)
                   for c in h.candidates)


def test_grid_starts_at_defaults_uses_one_seed_and_never_repeats():
    h = run_oracle(cpu_hunt(budget=12, strategy="grid"), lambda c: False)
    defaults = {d.name: d.default for d in h.search_space.dimensions}
    assert h.candidates[0].controls == defaults
    assert len({c.seed for c in h.candidates}) == 1
    keys = [tuple(sorted(c.controls.items())) for c in h.candidates]
    assert len(keys) == len(set(keys))


def test_grid_can_establish_boundary_with_shared_seed():
    from ghost_trials.hunt import empirical_boundary
    h = run_oracle(cpu_hunt(budget=12, strategy="grid"), lambda c: c["object_mass_kg"] > 0.6)
    assert empirical_boundary(h) is not None


def test_cpu_near_miss_counts_as_task_success_for_regression():
    metrics = TrialMetrics(time_to_react_ms=None, min_clearance_m=None, task_completed=True, fall_or_collision=False,
                           evidence_origin="synthetic", robot_metrics={"object_final_x_m": 0.645})
    trial = Trial(trial_id="trl_near", scenario_id="scn_test", status=TrialStatus.DONE, metrics=metrics)
    assert observed_outcome(trial, allow_synthetic_fixture=True)[0] == "near_failure"
    from ghost_trials.hunt import PASSING_OUTCOMES
    assert "near_failure" in PASSING_OUTCOMES


def test_each_case_gets_the_bracket_on_its_own_line():
    from ghost_trials.hunt import empirical_boundary
    h = run_oracle(cpu_hunt(budget=12, strategy="grid"),
                   lambda c: c["object_position_x_m"] < 0.36 or c["surface_friction"] > 1.0)
    position_fail = next(c for c in h.candidates if c.outcome == "failure" and c.controls["object_position_x_m"] < 0.36
                         and c.controls["surface_friction"] <= 1.0)
    friction_fail = next(c for c in h.candidates if c.outcome == "failure" and c.controls["surface_friction"] > 1.0
                         and c.controls["object_position_x_m"] >= 0.36)
    assert empirical_boundary(h, anchor=position_fail).dimension == "object_position_x_m"
    assert empirical_boundary(h, anchor=friction_fail).dimension == "surface_friction"


def test_legacy_grid_hunt_keeps_its_original_order():
    h = cpu_hunt(budget=9, strategy="grid")
    legacy = TrialCandidate(sequence=1, phase="explore", seed=123,
                            controls={d.name: d.minimum for d in h.search_space.dimensions})
    h.candidates.append(legacy)
    second = HuntPlanner(h).next()
    dims = h.search_space.dimensions
    assert second.controls[dims[0].name] == dims[0].default
