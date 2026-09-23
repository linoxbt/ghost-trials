from pathlib import Path

import pytest

from ghost_trials.adapters import DeterministicIsaacSimulator, LocalRubricJudge, LocalScenarioGenerator
from ghost_trials.models import ScenarioCreate, ScoreCategory, Severity, TrialStatus
from ghost_trials.pipeline import CertificationPipeline
from ghost_trials.store import TrialStore


@pytest.mark.asyncio
async def test_pipeline_is_replayable_and_persists(tmp_path: Path):
    store = TrialStore(tmp_path / "state.json")
    events = []

    async def publish(event):
        events.append(event)

    pipeline = CertificationPipeline(
        store, LocalScenarioGenerator(), DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0
    )
    scenario, trial = await pipeline.create(
        ScenarioCreate(prompt="A heavy box falls from a shelf", severity=Severity.HIGH, seed=42)
    )
    await pipeline.run(trial.trial_id)

    result = store.trials[trial.trial_id]
    assert result.status == TrialStatus.DONE
    assert result.score_category in ScoreCategory
    assert result.metrics is not None
    assert [event.status for event in events] == [
        TrialStatus.GENERATING, TrialStatus.SIMULATING, TrialStatus.SCORING, TrialStatus.DONE
    ]

    replay = await DeterministicIsaacSimulator().run(store.scenarios[scenario.scenario_id])
    assert replay == result.metrics

    restored = TrialStore(tmp_path / "state.json")
    await restored.load()
    assert restored.trials[trial.trial_id].metrics == result.metrics


@pytest.mark.asyncio
async def test_local_judge_uses_metric_thresholds():
    generator = LocalScenarioGenerator()
    scenario = await generator.generate("scn_1", "A cart slowly blocks the aisle", Severity.LOW, 1)
    simulator = DeterministicIsaacSimulator()
    result = await LocalRubricJudge().judge(scenario, await simulator.run(scenario))
    assert 0 <= result.confidence <= 1
    assert str(result.score_category) in {item.value for item in ScoreCategory}


@pytest.mark.asyncio
async def test_create_does_not_wait_for_generation_and_records_failure(tmp_path):
    class UnavailableGenerator:
        calls = 0

        async def generate(self, *args):
            self.calls += 1
            raise RuntimeError("Cosmos unavailable")

    generator = UnavailableGenerator()
    store = TrialStore(tmp_path / "state.json")
    events = []

    async def publish(event):
        events.append(event.status)

    pipeline = CertificationPipeline(
        store, generator, DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0
    )
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A box falls from a shelf"))
    assert generator.calls == 0
    assert scenario.structured_description.hazard_type == "pending_generation"
    assert trial.status == TrialStatus.QUEUED
    await pipeline.run(trial.trial_id)
    assert generator.calls == 1
    assert trial.status == TrialStatus.ERROR
    assert trial.error == "Cosmos unavailable"
    assert trial.metrics is None
    assert events == [TrialStatus.GENERATING, TrialStatus.ERROR]


@pytest.mark.asyncio
async def test_replay_preserves_scenario_without_regeneration(tmp_path):
    store = TrialStore(tmp_path / "replay.json")
    async def publish(event):
        pass
    pipeline = CertificationPipeline(store, LocalScenarioGenerator(), DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0)
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A heavy box falls from a shelf", seed=42))
    await pipeline.run(trial.trial_id)
    class NeverGenerate:
        async def generate(self, *args):
            raise AssertionError("Replay must not regenerate the scenario")
    pipeline.generator = NeverGenerate()
    reused, replay = await pipeline.replay(trial)
    await pipeline.run(replay.trial_id)
    assert reused.scenario_id == scenario.scenario_id
    assert replay.replay_of == trial.trial_id
    assert replay.metrics == trial.metrics
    assert replay.status == TrialStatus.DONE
    assert replay.trial_id != trial.trial_id
