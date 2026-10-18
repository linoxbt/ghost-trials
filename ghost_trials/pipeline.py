import asyncio
import random
import uuid
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from .adapters import ExecutionBlocked, ScenarioGenerator, Simulator, TrialJudge
from .models import LiveEvent, ModelReview, Scenario, ScenarioCreate, Severity, StructuredDescription, Trial, TrialStatus
from .store import TrialStore
from .evaluation import RUBRIC_VERSION, CPU_RUBRIC_VERSION, guard_judgment


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

    async def create(self, request: ScenarioCreate, *, persist=True):
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
                      policy_name=self.policy_name, rubric_version=CPU_RUBRIC_VERSION if getattr(self.simulator, "accepts_trial", False) else RUBRIC_VERSION)
        if persist:
            await self.store.put_scenario(scenario)
            await self.store.put_trial(trial)
        return scenario, trial

    async def run(self, trial_id: str) -> None:
        async with self._run_lock:
            await self._run(trial_id)

    async def replay(self, original: Trial, *, persist=True):
        if original.execution_mode == "physical":
            raise ValueError("A physical replay requires a new on-site recording; this server cannot actuate a robot")
        if original.status not in {TrialStatus.DONE, TrialStatus.BLOCKED}:
            raise ValueError("Only a completed or blocked trial can be replayed")
        scenario = self.store.scenarios[original.scenario_id]
        if scenario.structured_description.hazard_type == "pending_generation":
            raise ValueError("Scenario generation must finish before reusing a scenario")
        trial = Trial(trial_id=f"trl_{uuid.uuid4().hex[:12]}", scenario_id=scenario.scenario_id,
                      organization_id=original.organization_id,
                      embodiment=self.embodiment, policy_name=original.policy_name if getattr(self.simulator, "accepts_trial", False) else self.policy_name,
                      rubric_version=original.rubric_version, replay_of=original.trial_id)
        if persist:
            await self.store.put_trial(trial)
        return scenario, trial

    async def _run(self, trial_id: str) -> None:
        trial = self.store.trials[trial_id]
        scenario = self.store.scenarios[trial.scenario_id]
        try:
            if trial.execution_mode == "physical":
                from .physical import RecordingSetup, verify_recording
                import json
                with self.store.connect() as db:
                    row = db.execute("SELECT payload FROM records WHERE kind='physical_session' AND id=?",
                                     (trial.physical_session_id,)).fetchone()
                session = json.loads(row[0]) if row else None
                if (not session or session["status"] != "validated"
                        or session["organization_id"] != trial.organization_id or session["trial_id"] != trial.trial_id):
                    raise ExecutionBlocked(["Validated, organization-owned physical recording"])
                root = self.physical_settings.ghost_artifact_root / "physical" / trial.physical_session_id
                metrics, verification = await asyncio.to_thread(verify_recording, root,
                    RecordingSetup.model_validate(session["setup"]), session["manifest"])
                metrics.simulation_video_url = trial.metrics.simulation_video_url
                metrics.trace_url = trial.metrics.trace_url
                trial.metrics = metrics
                trial.evidence_verification = verification
                await self._score(trial, scenario)
                return
            if not trial.replay_of:
                await self._status(trial, TrialStatus.GENERATING, "Generating scenario and video")
                planned_recipe = scenario.execution_recipe
                scenario = await self.generator.generate(
                    scenario.scenario_id, scenario.prompt, scenario.requested_severity, scenario.seed
                )
                if getattr(self.simulator, "accepts_trial", False) and planned_recipe is None:
                    from .cpu_robot import recipe
                    scenario.execution_recipe = recipe(scenario.seed)
                if planned_recipe is not None:
                    if planned_recipe.get("kind") == "object_positioning":
                        from .cpu_robot import validate_recipe
                        validate_recipe(planned_recipe, scenario.seed)
                    else:
                        from workers.isaac.hazards import compile_hazard
                    if scenario.structured_description.hazard_type != planned_recipe.get("kind"):
                        raise ValueError("Generated hazard type differs from the requested trial; no robot trial submitted")
                    scenario.execution_recipe = planned_recipe
                    if planned_recipe.get("kind") != "object_positioning":
                        compile_hazard(scenario.model_dump(mode="json"))
                    if scenario.generation_provenance:
                        scenario.generation_provenance["video_recipe_alignment"] = "illustrative_only; execution recipe independently parameterized"
                scenario.organization_id = trial.organization_id
                await self.store.put_scenario(scenario)
            await asyncio.sleep(self.delay)
            await self._status(trial, TrialStatus.SIMULATING, "Running robot policy trial")
            measured = await (self.simulator.run(scenario, trial) if getattr(self.simulator, "accepts_trial", False)
                              else self.simulator.run(scenario))
            if getattr(self, "require_robot_evidence", False) and measured.evidence_origin != "simulator":
                raise ExecutionBlocked(["Verified robot-policy telemetry; synthetic metrics are prohibited in live mode"])
            if getattr(self, "evidence_repository", None) is not None:
                candidate = trial.model_copy(update={"metrics": measured})
                verification = await self.evidence_repository.capture(candidate, scenario, self.simulator.last_result)
                measured = candidate.metrics
                trial.evidence_verification = verification
            trial.metrics = measured
            await self.store.put_trial(trial)
            await self._score(trial, scenario)
        except ExecutionBlocked as exc:
            trial.metrics = None
            trial.error = str(exc)
            await self._status(trial, TrialStatus.BLOCKED, trial.error)
        except Exception as exc:
            if trial.status == TrialStatus.SIMULATING or (trial.execution_mode == "physical" and trial.status != TrialStatus.SCORING):
                # An invalid/unretained worker response is not measured evidence.
                trial.metrics = None
            if getattr(self, "redact_errors", False):
                logging.getLogger(__name__).error("pipeline_failed trial_id=%s error_type=%s", trial_id, type(exc).__name__)
                trial.error = "Pipeline stage failed; contact the operator with this trial ID."
            else:
                trial.error = str(exc) or type(exc).__name__
            await self._status(trial, TrialStatus.ERROR, "Trial pipeline failed")

    async def _score(self, trial, scenario):
        await asyncio.sleep(self.delay)
        await self._status(trial, TrialStatus.SCORING, "Safety judge is reviewing recorded telemetry")
        result = await self.judge.judge(scenario, trial.metrics)
        trial.judge_assessment = result
        result = guard_judgment(trial, scenario, result)
        trial.score_category, trial.confidence = result.score_category, result.confidence
        trial.tier_used, trial.reasoning_trace = result.tier_used, result.reasoning_trace
        reviewer = getattr(self, "model_reviewer", None)
        if reviewer is not None:
            try:
                trial.model_review = await reviewer.review(trial, scenario)
            except Exception:
                # Inference infrastructure cannot invalidate a measured robot trial.
                logging.getLogger(__name__).error("cpu_model_review_failed trial_id=%s", trial.trial_id)
                trial.model_review = ModelReview(status="provider_error")
        trial.completed_at = datetime.now(timezone.utc)
        await self._status(trial, TrialStatus.DONE, "Evaluation record saved; review evidence and limitations")

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
