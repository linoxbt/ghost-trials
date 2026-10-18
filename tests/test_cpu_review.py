"""Real physics evidence with a contract-tested Nebius boundary; no paid requests."""
import json
from pathlib import Path

import httpx
import pytest

from ghost_trials.accounts import Accounts
from ghost_trials.config import Settings
from ghost_trials.cpu_evidence import CpuEvidenceRepository, verify_cpu_bundle
from ghost_trials.cpu_review import CpuNemotronReviewer
from ghost_trials.cpu_robot import CpuMujocoSimulator, CpuScenarioGenerator, recipe
from ghost_trials.cpu_robot import CpuMeasuredJudge
from ghost_trials.durable import DurableStore
from ghost_trials.models import ScenarioCreate, Trial, TrialStatus
from ghost_trials.pipeline import CertificationPipeline
from scripts.cpu_live_review import run as run_cpu_review_probe


async def verified_trial(tmp_path):
    settings = Settings(ghost_artifact_root=tmp_path / "artifacts",
                        ghost_data_path=tmp_path / "state.sqlite3",
                        ghost_cpu_model_review_enabled=True, nebius_api_key="test-key",
                        ghost_live_execution_enabled=True,
                        ghost_provider_spending_controls_confirmed=True,
                        ghost_platform_budget_cents=20,
                        ghost_cpu_model_review_reservation_cents=10)
    store = DurableStore(settings.ghost_data_path)
    Accounts(store, settings).allocate_budget("legacy", 20)
    scenario = await CpuScenarioGenerator().generate("scn_review", "position a block", None, 42)
    scenario.execution_recipe = recipe(42)
    trial = Trial(trial_id="trl_review", scenario_id=scenario.scenario_id,
                  embodiment="GHOST_GANTRY_XY", policy_name="gantry-push-v1")
    simulator = CpuMujocoSimulator()
    trial.metrics = await simulator.run(scenario, trial)
    trial.evidence_verification = await CpuEvidenceRepository(settings).capture(trial, scenario, simulator.last_result)
    return settings, store, scenario, trial


@pytest.mark.asyncio
async def test_real_cpu_evidence_gets_one_bounded_model_review(tmp_path):
    settings, store, scenario, trial = await verified_trial(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url.path.endswith("/chat/completions")
        assert payload["max_tokens"] == 512 and payload["model"] == settings.nebius_super_model
        evidence = json.loads(payload["messages"][1]["content"])
        assert evidence["verification_status"] == "cpu_trace_metrics_verified"
        assert evidence["measurements"]["object_final_x_m"] == trial.metrics.robot_metrics["object_final_x_m"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "suggested_outcome": "fail" if trial.metrics.task_completed else "pass",
            "interpretation": "The measured final block position and task result disagree with this model suggestion.",
            "cited_metrics": {"object_final_x_m": trial.metrics.robot_metrics["object_final_x_m"]},
            "confidence": .7})}}], "usage": {"prompt_tokens": 130, "completion_tokens": 47}})

    reviewer = CpuNemotronReviewer(settings, store, httpx.MockTransport(handler))
    review = await reviewer.review(trial, scenario)
    assert review.status == "complete" and review.disagrees_with_measurement
    assert review.evidence_digest and review.prompt_tokens == 130
    assert trial.metrics.task_completed is True and len(calls) == 1
    assert (await reviewer.review(trial, scenario)).status == "unavailable"
    assert len(calls) == 1 and Accounts(store, settings).budget("legacy")["used_cents"] == 10


@pytest.mark.asyncio
async def test_cpu_review_budget_and_provider_failure_never_change_measured_trial(tmp_path):
    settings, store, scenario, trial = await verified_trial(tmp_path)
    Accounts(store, settings).allocate_budget("legacy", 0)
    reviewer = CpuNemotronReviewer(settings, store, httpx.MockTransport(lambda _: pytest.fail("No request expected")))
    assert (await reviewer.review(trial, scenario)).status == "budget_exhausted"
    assert trial.metrics.task_completed is True
    Accounts(store, settings).allocate_budget("legacy", 20)
    failing = CpuNemotronReviewer(settings, store, httpx.MockTransport(lambda _: httpx.Response(503)))
    assert (await failing.review(trial, scenario)).status == "provider_error"
    assert trial.metrics.task_completed is True


@pytest.mark.asyncio
async def test_cpu_review_rejects_unverified_and_invented_metric(tmp_path):
    settings, store, scenario, trial = await verified_trial(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "suggested_outcome": "pass", "interpretation": "The block entered the target band in simulation.",
            "cited_metrics": {"object_final_x_m": 99.0}, "confidence": .99})}}]})

    reviewer = CpuNemotronReviewer(settings, store, httpx.MockTransport(handler))
    trial.evidence_verification = None
    assert (await reviewer.review(trial, scenario)).status == "unavailable" and not calls
    trial.evidence_verification = {"status": "cpu_trace_metrics_verified",
                                   "checkpoint_digest": trial.metrics.policy_checkpoint_digest}
    assert (await reviewer.review(trial, scenario)).status == "invalid_response"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cpu_pipeline_finishes_measured_trial_when_nebius_fails(tmp_path):
    settings, store, _, _ = await verified_trial(tmp_path)
    pipeline = CertificationPipeline(store, CpuScenarioGenerator(), CpuMujocoSimulator(),
                                     CpuMeasuredJudge(), lambda _: async_noop(), delay_seconds=0,
                                     embodiment="GHOST_GANTRY_XY", policy_name="gantry-push-v1")
    pipeline.evidence_repository = CpuEvidenceRepository(settings)
    pipeline.model_reviewer = CpuNemotronReviewer(settings, store,
        httpx.MockTransport(lambda _: httpx.Response(503)))
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="position a block", seed=43))
    await pipeline.run(trial.trial_id)
    recorded = store.trials[trial.trial_id]
    assert recorded.status == TrialStatus.DONE
    assert recorded.metrics.task_completed is True
    assert recorded.evidence_verification["status"] == "cpu_trace_metrics_verified"
    assert recorded.model_review.status == "provider_error"
    assert recorded.score_category.value == "avoided"  # legacy API field; UI renders task pass


@pytest.mark.asyncio
async def test_cpu_pipeline_persists_real_physics_and_separate_model_interpretation(tmp_path):
    settings, store, _, _ = await verified_trial(tmp_path)

    def handler(request):
        evidence = json.loads(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "suggested_outcome": evidence["deterministic_outcome"],
            "interpretation": "The measured block position supports the recorded task outcome.",
            "cited_metrics": {"object_final_x_m": evidence["measurements"]["object_final_x_m"]},
            "confidence": .72})}}], "usage": {"prompt_tokens": 120, "completion_tokens": 35}})

    pipeline = CertificationPipeline(store, CpuScenarioGenerator(), CpuMujocoSimulator(),
                                     CpuMeasuredJudge(), lambda _: async_noop(), delay_seconds=0,
                                     embodiment="GHOST_GANTRY_XY", policy_name="gantry-push-v1")
    pipeline.evidence_repository = CpuEvidenceRepository(settings)
    pipeline.model_reviewer = CpuNemotronReviewer(settings, store, httpx.MockTransport(handler))
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="position a block", seed=44))
    await pipeline.run(trial.trial_id)
    restored = DurableStore(settings.ghost_data_path)
    await restored.load()
    saved = restored.trials[trial.trial_id]
    assert saved.status == TrialStatus.DONE
    assert saved.model_review.status == "complete"
    assert saved.model_review.evidence_digest and saved.model_review.model_id == settings.nebius_super_model
    assert saved.model_review.suggested_outcome == ("pass" if saved.metrics.task_completed else "fail")
    assert saved.evidence_verification["status"] == "cpu_trace_metrics_verified"


@pytest.mark.asyncio
async def test_operator_probe_retains_one_actual_passing_cpu_trial_without_paid_model(tmp_path):
    output = tmp_path / "operator-probe"
    report = await run_cpu_review_probe(output, live_nebius=False, seed=42)
    assert report["status"] == "done" and report["task_completed"] is True
    assert report["object_final_x_m"] == pytest.approx(0.729056, abs=0.005)
    assert report["evidence_verification"] == "cpu_trace_metrics_verified"
    assert report["model_review_status"] == "disabled"
    store = DurableStore(output / "state.sqlite3")
    await store.load()
    saved = store.trials[report["trial_id"]]
    assert saved.metrics.policy_checkpoint_digest == report["checkpoint_digest"]
    assert (output / "artifacts" / "trials" / saved.trial_id / "telemetry.jsonl").exists()


def test_public_reference_is_actual_verifiable_physics_and_not_customer_score():
    bundle = Path(__file__).resolve().parents[1] / "static" / "reference" / "gantry-v1"
    index = json.loads((bundle / "index.json").read_text())
    summary = json.loads((bundle / "summary.json").read_text())
    assert index["customer_score_eligible"] is False
    assert index["model_review_status"] == "not_requested"
    assert index["object_final_x_m"] == summary["object_final_x_m"]
    assert summary["task_completed"] is True
    assert verify_cpu_bundle(bundle, index["checkpoint_digest"])["status"] == "cpu_trace_metrics_verified"


async def async_noop():
    return None
