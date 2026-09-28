"""Contract tests, not evidence that a GPU or hosted provider actually ran."""
import base64
import json

import httpx
import pytest

from ghost_trials.adapters import ExecutionBlocked, LocalScenarioGenerator, LocalRubricJudge
from ghost_trials.config import Settings
from ghost_trials.models import ScenarioCreate, TrialStatus
from ghost_trials.pipeline import CertificationPipeline
from ghost_trials.production import CosmosVideoClient, CosmosScenarioGenerator, IsaacRemoteSimulator
from ghost_trials.store import TrialStore


@pytest.mark.asyncio
async def test_hosted_cosmos_contract_accepts_nvidia_key():
    video = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom"
    def handler(request):
        assert str(request.url) == "https://ai.api.nvidia.com/v1/cosmos/nvidia/cosmos3-nano"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model_mode"] == "text2video"
        assert body["num_frames"] == 25
        assert body["num_inference_steps"] == 35
        assert "num_output_frames" not in body
        return httpx.Response(200, json={"b64_video": base64.b64encode(video).decode()})
    settings = Settings(_env_file=None, cosmos_api_style="nvidia_catalog", nvidia_api_key="test-key", cosmos_num_frames=25)
    client = CosmosVideoClient(settings, httpx.MockTransport(handler))
    assert await client.generate("A box falls beside a walking robot", 42) == video
    assert await client.ready() is False


@pytest.mark.asyncio
async def test_missing_cosmos_key_blocks_before_paid_reasoner(tmp_path):
    class NoReasoner:
        async def expand(self, *args):
            pytest.fail("Must not bill reasoner before checking video credentials")
    generator = CosmosScenarioGenerator(
        Settings(_env_file=None, cosmos_api_style="nvidia_catalog", ghost_artifact_root=tmp_path),
        reasoner=NoReasoner(),
    )
    with pytest.raises(ExecutionBlocked, match="NVIDIA_API_KEY"):
        await generator.generate("scn_missing", "A box falls", None, 42)


@pytest.mark.asyncio
async def test_gpu_block_preserves_scenario_never_invents_metrics_or_calls_judge(tmp_path):
    class NoJudge:
        async def judge(self, *args):
            pytest.fail("No robot evidence: no judge inference or finding allowed")
    async def publish(event):
        pass
    store = TrialStore(tmp_path / "state.json")
    pipeline = CertificationPipeline(store, LocalScenarioGenerator(),
        IsaacRemoteSimulator(Settings(_env_file=None)), NoJudge(), publish, 0)
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A box falls"))
    await pipeline.run(trial.trial_id)
    assert trial.status == TrialStatus.BLOCKED
    assert trial.metrics is None and trial.score_category is None
    assert "GPU policy worker" in trial.error
    assert store.scenarios[scenario.scenario_id].structured_description.hazard_type != "pending_generation"
    saved, resumed = await pipeline.replay(trial)
    assert saved.scenario_id == scenario.scenario_id
    assert resumed.replay_of == trial.trial_id


@pytest.mark.asyncio
async def test_live_pipeline_rejects_synthetic_metrics(tmp_path):
    from ghost_trials.adapters import DeterministicIsaacSimulator
    async def publish(event):
        pass
    store = TrialStore(tmp_path / "state.json")
    pipeline = CertificationPipeline(store, LocalScenarioGenerator(), DeterministicIsaacSimulator(),
        LocalRubricJudge(), publish, 0)
    pipeline.require_robot_evidence = True
    _, trial = await pipeline.create(ScenarioCreate(prompt="A box falls"))
    await pipeline.run(trial.trial_id)
    assert trial.status == TrialStatus.BLOCKED
    assert trial.metrics is None and trial.judge_assessment is None


@pytest.mark.asyncio
async def test_worker_metrics_not_published_before_evidence_validation(tmp_path):
    from ghost_trials.models import TrialMetrics
    class Worker:
        last_result = {}
        async def run(self, scenario):
            return TrialMetrics(time_to_react_ms=300, min_clearance_m=0.7,
                task_completed=True, fall_or_collision=False, evidence_origin="simulator")
    class RejectEvidence:
        async def capture(self, candidate, scenario, result):
            assert candidate.metrics is not None
            assert store.trials[candidate.trial_id].metrics is None
            raise ValueError("Invalid telemetry")
    class NoJudge:
        async def judge(self, *args):
            pytest.fail("Invalid evidence must not reach the judge")
    async def publish(event):
        pass
    store = TrialStore(tmp_path / "state.json")
    pipeline = CertificationPipeline(store, LocalScenarioGenerator(), Worker(), NoJudge(), publish, 0)
    pipeline.evidence_repository = RejectEvidence()
    _, trial = await pipeline.create(ScenarioCreate(prompt="A box falls"))
    await pipeline.run(trial.trial_id)
    assert trial.status == TrialStatus.ERROR and trial.metrics is None


@pytest.mark.asyncio
async def test_restart_preserves_blocked_trial(tmp_path):
    from ghost_trials.jobs import JobRunner
    from ghost_trials.models import Trial
    store = TrialStore(tmp_path / "state.json")
    trial = Trial(trial_id="trl_blocked", scenario_id="scn_blocked", status=TrialStatus.BLOCKED)
    await store.put_trial(trial)
    store.job = lambda trial_id: {"state": "blocked"}
    await JobRunner(store, None, None).recover()
    assert store.trials[trial.trial_id].status == TrialStatus.BLOCKED
