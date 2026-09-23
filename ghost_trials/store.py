import asyncio
import json
from pathlib import Path

from .models import Scenario, Trial


class TrialStore:
    def __init__(self, path: Path):
        self.path = path
        self.scenarios: dict[str, Scenario] = {}
        self.trials: dict[str, Trial] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text())
        self.scenarios = {
            item["scenario_id"]: Scenario.model_validate(item)
            for item in payload.get("scenarios", [])
        }
        self.trials = {
            item["trial_id"]: Trial.model_validate(item)
            for item in payload.get("trials", [])
        }

    async def save(self) -> None:
        async with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "scenarios": [item.model_dump(mode="json") for item in self.scenarios.values()],
                "trials": [item.model_dump(mode="json") for item in self.trials.values()],
            }
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, indent=2))
            temp.replace(self.path)

    async def put_scenario(self, scenario: Scenario) -> None:
        self.scenarios[scenario.scenario_id] = scenario
        await self.save()

    async def put_trial(self, trial: Trial) -> None:
        self.trials[trial.trial_id] = trial
        await self.save()

    def list_trials(self) -> list[Trial]:
        return sorted(self.trials.values(), key=lambda item: item.started_at, reverse=True)
