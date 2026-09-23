import asyncio
import random
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from .adapters import ScenarioGenerator, Simulator, TrialJudge
from .models import LiveEvent, Scenario, ScenarioCreate, Severity, StructuredDescription, Trial, TrialStatus
from .store import TrialStore
from .evaluation import RUBRIC_VERSION, guard_judgment


Publish = Callable[[LiveEvent], Awaitable[None]]


class CertificationPipeline:
    def __init__(
        self,
        store: TrialStore,
        generator: ScenarioGenerator,
        simulator: Simulator,
        judge: TrialJudge,
        publish: Publish,
        delay_seconds: float = 0.35,
        embodiment: str = "UNITREE_G1_SONIC",
        policy_name: str = "development-fixture",
    ):
        self.store = store
        self.generator = generator
        self.simulator = simulator
        self.judge = judge
        self.publish = publish
        self.delay = delay_seconds
        self.embodiment = embodiment
        self.policy_name = policy_name
        self._run_lock = asyncio.Lock()

    async def create(self, request: ScenarioCreate):
        suffix = uuid.uuid4().hex[:12]
        scenario_id, trial_id = f"scn_{suffix}", f"trl_{suffix}"
        seed = request.seed if request.seed is not None else random.SystemRandom().randrange(2_147_483_647)
        scenario = Scenario(
            scenario_id=scenario_id, prompt=request.prompt, seed=seed,
            severity_tag=request.severity or Severity.MEDIUM, requested_severity=request.severity,
            structured_description=StructuredDescription(
                objects=[], hazard_type="pending_generation", severity=request.severity or Severity.MEDIUM,
                expected_safe_behavior="Pending scenario generation",
            ),
        )
        trial = Trial(trial_id=trial_id, scenario_id=scenario_id, embodiment=self.embodiment,
                      policy_name=self.policy_name, rubric_version=RUBRIC_VERSION)
        await self.store.put_scenario(scenario)
        await self.store.put_trial(trial)
        return scenario, trial

    async def run(self, trial_id: str) -> None:
        async with self._run_lock:
            await self._run(trial_id)

    async def replay(self, original: Trial):
        if original.status != TrialStatus.DONE:
            raise ValueError("Only a completed trial can be replayed")
        scenario = self.store.scenarios[original.scenario_id]
        trial = Trial(trial_id=f"trl_{uuid.uuid4().hex[:12]}", scenario_id=scenario.scenario_id,
                      embodiment=self.embodiment, policy_name=self.policy_name,
                      rubric_version=RUBRIC_VERSION, replay_of=original.trial_id)
        await self.store.put_trial(trial)
        return scenario, trial

    async def _run(self, trial_id: str) -> None:
        trial = self.store.trials[trial_id]
        scenario = self.store.scenarios[trial.scenario_id]
        try:
            if not trial.replay_of:
                await self._status(trial, TrialStatus.GENERATING, "Generating scenario and video")
                scenario = await self.generator.generate(
                    scenario.scenario_id, scenario.prompt, scenario.requested_severity, scenario.seed
                )
                await self.store.put_scenario(scenario)
            await asyncio.sleep(self.delay)
            await self._status(trial, TrialStatus.SIMULATING, "Running robot policy trial")
            trial.metrics = await self.simulator.run(scenario)
            await self.store.put_trial(trial)
            await asyncio.sleep(self.delay)
            await self._status(trial, TrialStatus.SCORING, "Safety judge is reviewing telemetry")
            result = await self.judge.judge(scenario, trial.metrics)
            trial.judge_assessment = result
            result = guard_judgment(trial, scenario, result)
            trial.score_category = result.score_category
            trial.confidence = result.confidence
            trial.tier_used = result.tier_used
            trial.reasoning_trace = result.reasoning_trace
            trial.completed_at = datetime.now(timezone.utc)
            await self._status(trial, TrialStatus.DONE, "Evaluation record saved; review evidence and limitations")
        except Exception as exc:
            trial.error = str(exc) or type(exc).__name__
            await self._status(trial, TrialStatus.ERROR, "Trial pipeline failed")

    async def _status(self, trial: Trial, status: TrialStatus, message: str) -> None:
        trial.status = status
        await self.store.put_trial(trial)
        await self.publish(
            LiveEvent(
                trial_id=trial.trial_id,
                status=status,
                score_category=trial.score_category,
                message=message,
            )
        )
