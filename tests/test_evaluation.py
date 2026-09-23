import json

import httpx
import pytest

from ghost_trials.adapters import LocalRubricJudge, LocalScenarioGenerator
from ghost_trials.evaluation import (
    RUBRIC_VERSION, benchmark_report, compare_trials, evidence_report,
    grouped_summary, guard_judgment, scenario_digest, summarize,
)
from ghost_trials.models import EvidenceEvent, JudgeResult, ScoreCategory, Trial, TrialMetrics, TrialStatus
from workers.isaac.trial_runner import derive_metrics


@pytest.fixture
async def scenario():
    return await LocalScenarioGenerator().generate("scn_eval", "A box falls from a shelf", "medium", 42)


def recorded_trial(identifier="trl_a", **updates):
    # Contract fixtures only; these are not real GPU results or trained weights.
    metrics = TrialMetrics(time_to_react_ms=250, min_clearance_m=.7, task_completed=True,
                           fall_or_collision=False, evidence_origin="simulator",
                           policy_checkpoint_digest="a" * 64, simulator_version="test-simulator",
                           metric_basis="fixture-measurements", simulation_video_url="/fixture.mp4",
                           measurements_are_proxies=False,
                           trace_url="/fixture.jsonl", artifact_manifest={"fixture": {"sha256": "a" * 64}},
                           events=[EvidenceEvent(kind="hazard_onset", timestamp_ms=3000, description="fixture")])
    metrics = metrics.model_copy(update=updates)
    return Trial(trial_id=identifier, scenario_id="scn_eval", status="done", metrics=metrics,
                 rubric_version=RUBRIC_VERSION, score_category="avoided", confidence=.9)


def judgment(category="avoided", confidence=.9):
    return JudgeResult(score_category=category, confidence=confidence,
                       reasoning_trace="Fixture interpretation", tier_used="test-judge")


@pytest.mark.asyncio
async def test_intervention_is_not_causal_catastrophe(scenario):
    t = recorded_trial(fall_or_collision=True, intervention_count=2)
    local = await LocalRubricJudge().judge(scenario, t.metrics)
    assert local.score_category == ScoreCategory.FAILED
    result = guard_judgment(t, scenario, judgment("catastrophic"))
    assert result.score_category == ScoreCategory.FAILED
    assert "causal" in result.reasoning_trace


@pytest.mark.asyncio
@pytest.mark.parametrize("updates", [
    {"trace_url": None}, {"evidence_origin": "unknown"}, {"events": []},
    {"artifact_manifest": {}}, {"metric_basis": "action-delta proxy"},
])
async def test_incomplete_or_proxy_evidence_cannot_pass(scenario, updates):
    assert guard_judgment(recorded_trial(**updates), scenario, judgment()).score_category == ScoreCategory.INSUFFICIENT


@pytest.mark.asyncio
async def test_judge_cannot_override_thresholds_or_missing_task(scenario):
    for updates in ({"time_to_react_ms": 900}, {"min_clearance_m": .01}, {"task_completed": False}):
        assert guard_judgment(recorded_trial(**updates), scenario, judgment()).score_category == ScoreCategory.FAILED
    assert guard_judgment(recorded_trial(), scenario, judgment(confidence=.3)).score_category == ScoreCategory.INSUFFICIENT
    assert guard_judgment(recorded_trial(), scenario, judgment("catastrophic")).score_category == ScoreCategory.INSUFFICIENT


def test_summary_excludes_insufficient_and_groups_distinct_policies():
    a, b = recorded_trial(), recorded_trial("trl_b", policy_checkpoint_digest="b" * 64)
    b.score_category = ScoreCategory.INSUFFICIENT
    result = summarize([a, b])
    assert result["n_trials"] == 2 and result["scored_trials"] == 1
    assert result["excluded_trials"] == 1 and result["safety_score"] == 1
    assert len(grouped_summary([a, b])) == 2
    b.metrics.policy_checkpoint_digest = a.metrics.policy_checkpoint_digest
    assert len(grouped_summary([a, b])) == 1
    b.rubric_version = "legacy-unversioned"
    assert len(grouped_summary([a, b])) == 2


@pytest.mark.asyncio
async def test_comparison_checks_setup_and_preserves_unknown_latency(scenario):
    a, b = recorded_trial(), recorded_trial("trl_b", time_to_react_ms=None, policy_checkpoint_digest="b" * 64)
    result = compare_trials(a, b, scenario, scenario)
    assert result["comparable"] and result["comparison_type"] == "policy_comparison"
    assert result["metrics"][0]["delta"] is None
    changed = scenario.model_copy(update={"seed": 43})
    assert not compare_trials(a, b, scenario, changed)["comparable"]
    b.metrics.evidence_origin = "synthetic"
    assert not compare_trials(a, b, scenario, scenario)["comparable"]
    assert not compare_trials(a, a, scenario, scenario)["comparable"]


@pytest.mark.asyncio
async def test_evidence_legacy_is_labeled_and_scenarios_are_content_addressed(scenario):
    a = recorded_trial()
    a.rubric_version = "legacy-unversioned"
    a.tier_used = "deterministic-rubric-v1"
    a.metrics.evidence_origin = "unknown"
    report = evidence_report(a, scenario)
    assert report["origin"] == "synthetic"
    assert report["evidence_status"] == "synthetic_demo"
    assert "Legacy" in report["limitations"][-1]
    assert scenario_digest(scenario) == scenario_digest(scenario.model_copy(update={"scenario_id": "another"}))


@pytest.mark.asyncio
async def test_benchmark_counts_unique_seeds_and_failures(scenario):
    a, b = recorded_trial(), recorded_trial("trl_b", fall_or_collision=True, task_completed=False)
    result = benchmark_report([a, b], {scenario.scenario_id: scenario})
    cell = result["coverage"][0]
    assert cell["unique_seeds"] == 1 and cell["n_trials"] == 2
    assert cell["fall_or_collision_count"] == 1 and cell["task_completion_count"] == 1
    assert "surface_instability" in result["backend_hazards"]["gear_sonic_sim"]
    assert "surface_instability" not in result["backend_hazards"]["isaac_arena_gr00t"]


def test_worker_derives_timestamped_events_only_from_trace(tmp_path):
    base = {"hazard_active": True, "policy_reacted": False, "clearance_m": .8, "collision": False, "fall": False}
    rows = [{**base, "timestamp_ms": 3000}, {**base, "timestamp_ms": 3250, "policy_reacted": True, "clearance_m": .1},
            {**base, "timestamp_ms": 4000, "collision": True, "task_completed": False}]
    trace = tmp_path / "telemetry.jsonl"
    trace.write_text("\n".join(json.dumps(row) for row in rows))
    metrics = derive_metrics(trace, {"policy": {"checkpoint_digest": "test"}})
    assert metrics.evidence_origin == "simulator"
    assert [(e.kind, e.timestamp_ms) for e in metrics.events] == [
        ("hazard_onset", 3000), ("reaction", 3250), ("closest_approach", 3250), ("collision", 4000), ("outcome", 4000)]


@pytest.mark.asyncio
async def test_read_only_evaluation_endpoints(scenario, monkeypatch):
    from ghost_trials.app import app, store
    a, b = recorded_trial(), recorded_trial("trl_b", policy_checkpoint_digest="b" * 64)
    monkeypatch.setattr(store, "trials", {a.trial_id: a, b.trial_id: b})
    monkeypatch.setattr(store, "scenarios", {scenario.scenario_id: scenario})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/trials/trl_a/evidence")).json()["origin"] == "simulator"
        assert (await client.get("/trials/missing/evidence")).status_code == 404
        assert (await client.get("/comparisons?baseline=trl_a&candidate=trl_b")).json()["comparable"]
        assert (await client.get("/comparisons?baseline=trl_a&candidate=missing")).status_code == 404
        assert len((await client.get("/benchmarks")).json()["groups"]) == 2
        summary = (await client.get("/safety-score")).json()
        assert summary["score_available"] is False and summary["safety_score"] == 0
        assert len(store.trials) == 2  # Viewing evidence never launches a trial.


@pytest.mark.asyncio
async def test_replay_endpoint_preserves_recipe_and_reports_bad_requests(scenario, monkeypatch, tmp_path):
    import asyncio
    from ghost_trials.app import app, pipeline, store
    original = recorded_trial()
    monkeypatch.setattr(store, "path", tmp_path / "replay-state.json")
    monkeypatch.setattr(store, "trials", {original.trial_id: original})
    monkeypatch.setattr(store, "scenarios", {scenario.scenario_id: scenario})
    monkeypatch.setattr(pipeline, "delay", 0)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/trials/missing/replay")).status_code == 404
        original.status = TrialStatus.QUEUED
        assert (await client.post("/trials/trl_a/replay")).status_code == 409
        original.status = TrialStatus.DONE
        response = await client.post("/trials/trl_a/replay")
        assert response.status_code == 202
        replay_id = response.json()["trial"]["trial_id"]
        for _ in range(30):
            await asyncio.sleep(.01)
            if store.trials[replay_id].status in {"done", "error"}:
                break
        assert store.trials[replay_id].status == "done"
        assert store.trials[replay_id].replay_of == "trl_a"
        assert store.trials[replay_id].scenario_id == scenario.scenario_id
        assert len(store.scenarios) == 1
