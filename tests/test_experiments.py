import pytest

from ghost_trials.adapters import LocalScenarioGenerator, LocalRubricJudge, DeterministicIsaacSimulator
from ghost_trials.experiments import SearchPlan, bounded_search
from ghost_trials.pipeline import CertificationPipeline
from ghost_trials.store import TrialStore


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["adaptive", "random", "grid"])
async def test_search_is_bounded_and_explicitly_synthetic(tmp_path, strategy):
    async def publish(event):
        pass
    store = TrialStore(tmp_path / "state.json")
    pipeline = CertificationPipeline(store, LocalScenarioGenerator(), DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0)
    plan = SearchPlan(strategy=strategy, max_trials=4)
    report = await bounded_search(plan, pipeline)
    assert report["executed_trials"] == 4
    assert not report["stopped_on_error"]
    assert all(g["origin"] == "synthetic" for g in report["benchmark"]["groups"])
    assert len({(r["severity"], r["seed"]) for r in report["observations"]}) == 4


@pytest.mark.asyncio
async def test_search_stops_at_provider_error_without_counting_robot_failure(tmp_path):
    class Offline:
        async def generate(self, *args):
            raise RuntimeError("Provider offline")
    async def publish(event):
        pass
    pipeline = CertificationPipeline(TrialStore(tmp_path / "state.json"), Offline(), DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0)
    report = await bounded_search(SearchPlan(max_trials=6), pipeline)
    assert report["executed_trials"] == 1 and report["stopped_on_error"]
    assert report["observations"][0]["observed_failure"] is None
    assert report["lowest_observed_failure"] is None


@pytest.mark.parametrize("seeds", [[1, 1], [-1], [2_147_483_648]])
def test_seed_bounds(seeds):
    with pytest.raises(ValueError):
        SearchPlan(seeds=seeds).candidates()
