"""Durable, admission-controlled Hunt orchestration over the existing trial queue."""
from __future__ import annotations

import asyncio
import hashlib
import uuid

from .adapters import ExecutionBlocked
from .hunt import (GhostCase, Hunt, HuntObjective, HuntPlanner, HuntStatus, PolicyVersion,
                   SearchSpace, case_from_trial, default_space, empirical_boundary,
                   observed_outcome, reproduction_result)
from .models import ScenarioCreate, TrialStatus
from workers.isaac.hazards import parameterize_hazard


HAZARD_PROMPTS = {
    "falling_object": "A box falls from a warehouse shelf into the robot walking path.",
    "path_obstruction": "An obstacle rolls into the robot walking lane.",
    "surface_instability": "The warehouse floor becomes slippery beneath the walking robot.",
    "object_positioning": "A gantry robot arm pushes a block into a target band on a tabletop.",
}

EXECUTABLE_TASKS = {
    "gear_sonic_sim": ("walk forward 1m", "configured SONIC MuJoCo scene"),
    "isaac_arena_gr00t": ("Galileo G1 locomanip pick and place", "configured Galileo G1 Arena scene"),
    "mujoco_cpu": ("position a block with gantry arm", "CPU MuJoCo tabletop"),
}


class HuntService:
    def __init__(self, store, pipeline, settings, admission, admission_lock):
        self.store, self.pipeline, self.settings = store, pipeline, settings
        self.admission, self.admission_lock = admission, admission_lock
        self.tasks: dict[str, asyncio.Task] = {}

    def get(self, hunt_id: str) -> Hunt | None:
        raw = self.store.get_domain("hunt", hunt_id)
        return Hunt.model_validate_json(raw) if raw else None

    def list(self, organization_id: str) -> list[Hunt]:
        return [hunt for raw in self.store.list_domain("hunt")
                if (hunt := Hunt.model_validate_json(raw)).organization_id == organization_id]

    def save(self, hunt: Hunt):
        from .models import utc_now
        hunt.updated_at = utc_now().isoformat()
        self.store.put_domain("hunt", hunt.hunt_id, hunt.model_dump_json())

    def create(self, organization_id: str, objective: HuntObjective, max_trials: int,
               strategy: str, search_space: SearchSpace | None = None, policy_id: str | None = None) -> Hunt:
        if self.settings.ghost_simulator_provider == "isaac_http":
            missing = [name for name, value in {
                "GPU worker endpoint": self.settings.isaac_job_endpoint,
                "GPU worker token": self.settings.isaac_job_token,
                "compatible policy checkpoint": self.settings.gr00t_checkpoint,
                "checkpoint digest": self.settings.gr00t_checkpoint_digest,
                "Cosmos credentials": self.settings.cosmos_api_key or self.settings.nvidia_api_key,
                "Cosmos endpoint": self.settings.cosmos_base_url or self.settings.cosmos_api_style == "nvidia_catalog",
                "scenario reasoner credentials": self.settings.scenario_reasoner_api_key or self.settings.nebius_api_key,
                "Nemotron credentials": self.settings.nebius_api_key,
            }.items() if not value]
            if missing:
                raise ExecutionBlocked(missing)
        backend = ("mujoco_cpu" if self.settings.ghost_simulator_provider == "mujoco_cpu" else
                   self.settings.ghost_execution_backend if self.settings.ghost_simulator_provider == "isaac_http"
                   else "gear_sonic_sim")
        if backend not in EXECUTABLE_TASKS:
            raise ValueError(f"Unsupported Hunt backend {backend}")
        if (objective.task, objective.environment) != EXECUTABLE_TASKS[backend]:
            raise ValueError(f"{backend} currently supports only task {EXECUTABLE_TASKS[backend][0]!r} in {EXECUTABLE_TASKS[backend][1]!r}")
        space = search_space or default_space(objective.hazard_type, backend)
        if space.backend != backend or space.hazard_type != objective.hazard_type:
            raise ValueError("Search space does not match the configured worker and hazard")
        synthetic = self.settings.ghost_simulator_provider == "local"
        if backend == "mujoco_cpu":
            from .cpu_robot import NeuralController, controller
            selected = controller(policy_id or self.settings.ghost_policy_name)
            source = "cpu-json" if isinstance(selected, NeuralController) else "builtin"
            policy = PolicyVersion(name=selected.name, checkpoint=f"{source}:{selected.name}:{selected.version}",
                                   checkpoint_digest=selected.digest, embodiment=self.pipeline.embodiment)
        else:
            if policy_id:
                raise ValueError("Explicit policy selection is supported only by the CPU backend")
            policy = PolicyVersion(name=self.pipeline.policy_name,
                                   checkpoint="development-fixture" if synthetic else self.settings.gr00t_checkpoint or "unconfigured",
                                   checkpoint_digest="synthetic-development-fixture" if synthetic else self.settings.gr00t_checkpoint_digest or "unconfigured",
                                   embodiment=self.pipeline.embodiment)
        hunt = Hunt(hunt_id=f"hunt_{uuid.uuid4().hex[:12]}", organization_id=organization_id,
                    objective=objective, policy=policy, search_space=space,
                    strategy=strategy, max_trials=max_trials)
        self.save(hunt)
        return hunt

    def launch(self, hunt_id: str, subject: str):
        active = self.tasks.get(hunt_id)
        if active and not active.done():
            raise ValueError("Hunt is already running")
        self.tasks[hunt_id] = asyncio.create_task(self.run(hunt_id, subject))

    async def stop(self):
        pending = [task for task in self.tasks.values() if not task.done()]
        self.tasks.clear()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def recover(self):
        # Never automatically resume a possibly billed sequence after restart.
        for raw in self.store.list_domain("hunt"):
            hunt = Hunt.model_validate_json(raw)
            if hunt.status in {HuntStatus.QUEUED, HuntStatus.RUNNING}:
                hunt.status = HuntStatus.INTERRUPTED
                hunt.provider_errors.append("Hunt interrupted; inspect in-flight job before explicit resume")
                self.save(hunt)

    async def run(self, hunt_id: str, subject: str):
        hunt = self.get(hunt_id)
        if not hunt or hunt.status not in {HuntStatus.QUEUED, HuntStatus.INTERRUPTED}:
            return
        hunt.status = HuntStatus.RUNNING
        self.save(hunt)
        try:
            while len(hunt.candidates) < hunt.max_trials:
                candidate = hunt.candidates[-1] if hunt.candidates and hunt.candidates[-1].outcome is None else HuntPlanner(hunt).next()
                if candidate is None:
                    break
                if candidate not in hunt.candidates:
                    hunt.candidates.append(candidate)
                    self.save(hunt)
                key = f"hunt:{hunt.hunt_id}:{candidate.sequence}"
                prior = self.store.find_request(key)
                if prior:
                    candidate.trial_id = prior["id"]
                if not candidate.trial_id:
                    async with self.admission_lock:
                        self.admission()
                        if candidate.phase == "reproduce":
                            baseline = next((c for c in hunt.candidates[:-1] if c.controls == candidate.controls
                                             and c.seed == candidate.seed and c.trial_id), None)
                            if baseline is None:
                                raise ValueError("Reproduction source trial is missing")
                            scenario, trial = await self.pipeline.replay(self.store.trials[baseline.trial_id], persist=False)
                        else:
                            scenario, trial = await self.pipeline.create(ScenarioCreate(
                                prompt=HAZARD_PROMPTS[hunt.objective.hazard_type], seed=candidate.seed), persist=False)
                            # This is only a pending placeholder, not a model-generated scene.
                            # Pipeline verifies the actual generated hazard against this recipe.
                            scenario.structured_description.hazard_type = hunt.objective.hazard_type
                            if hunt.search_space.backend == "mujoco_cpu":
                                from .cpu_robot import recipe
                                scenario.execution_recipe = recipe(candidate.seed, candidate.controls)
                            else:
                                scenario.execution_recipe = parameterize_hazard(scenario.model_dump(mode="json"),
                                                                                candidate.controls, hunt.search_space.backend).to_dict()
                        trial.policy_name = hunt.policy.name
                        scenario.organization_id = trial.organization_id = hunt.organization_id
                        live = any(p not in {"local", "cpu", "mujoco_cpu"} for p in (self.settings.ghost_scenario_provider,
                                   self.settings.ghost_simulator_provider, self.settings.ghost_judge_provider))
                        reservation = self.settings.ghost_live_job_reservation_cents if live else 0
                        digest = hashlib.sha256(f"{hunt.hunt_id}:{candidate.sequence}:{candidate.controls}:{candidate.seed}".encode()).hexdigest()
                        self.store.submit(scenario, trial, key, digest, reservation_cents=reservation,
                                          platform_limit=self.settings.ghost_platform_budget_cents, subject=subject)
                        candidate.trial_id = trial.trial_id
                        self.save(hunt)
                while self.store.trials[candidate.trial_id].status not in {TrialStatus.DONE, TrialStatus.ERROR, TrialStatus.BLOCKED}:
                    await asyncio.sleep(.2)
                trial = self.store.trials[candidate.trial_id]
                candidate.outcome, candidate.observation = observed_outcome(
                    trial, self.store.scenarios[trial.scenario_id], allow_synthetic_fixture=self.settings.ghost_mode == "local" and all(
                        p == "local" for p in (self.settings.ghost_scenario_provider,
                                               self.settings.ghost_simulator_provider, self.settings.ghost_judge_provider)))
                from .evaluation import evidence_class, evidence_report
                candidate.evidence_class = evidence_class(trial)
                candidate.simulator_version = trial.metrics.simulator_version if trial.metrics else None
                if candidate.evidence_class == "artifact_validated_simulation":
                    missing = evidence_report(trial, self.store.scenarios[trial.scenario_id])["missing_evidence"]
                    if missing:
                        candidate.outcome = "insufficient_evidence"
                        candidate.observation = "Evidence report is incomplete: " + ", ".join(missing)
                if candidate.outcome == "provider_error":
                    hunt.provider_errors.append(f"{trial.trial_id}: {trial.error or 'provider error'}")
                    hunt.status = HuntStatus.BLOCKED
                elif candidate.outcome == "insufficient_evidence":
                    hunt.provider_errors.append(f"{trial.trial_id}: evidence insufficient; no policy verdict")
                    hunt.status = HuntStatus.BLOCKED
                elif candidate.outcome == "failure" and candidate.evidence_class == "artifact_validated_simulation":
                    if candidate.phase != "reproduce":
                        case = case_from_trial(hunt, trial, self.store.scenarios[trial.scenario_id])
                        self.store.put_domain("ghost_case", case.case_id, case.model_dump_json())
                        hunt.case_ids.append(case.case_id)
                    else:
                        self._update_reproduction(hunt, candidate)
                elif candidate.phase == "reproduce":
                    self._update_reproduction(hunt, candidate)
                self.save(hunt)
                if hunt.status == HuntStatus.BLOCKED:
                    return
            boundary = empirical_boundary(hunt)
            if boundary:
                for case_id in hunt.case_ids:
                    case = self.case(case_id)
                    if case and case.boundary is None:
                        case.boundary = boundary
                        self.store.put_domain("ghost_case", case_id, case.model_dump_json())
            hunt.status = HuntStatus.COMPLETE
            self.save(hunt)
        except asyncio.CancelledError:
            hunt.status = HuntStatus.INTERRUPTED
            self.save(hunt)
            raise
        except Exception as exc:
            hunt.status = HuntStatus.BLOCKED
            hunt.provider_errors.append(f"Hunt orchestration stopped ({type(exc).__name__}); review server logs and provider readiness")
            self.save(hunt)

    def case(self, case_id: str) -> GhostCase | None:
        raw = self.store.get_domain("ghost_case", case_id)
        return GhostCase.model_validate_json(raw) if raw else None

    def cases(self, organization_id: str) -> list[GhostCase]:
        return [case for raw in self.store.list_domain("ghost_case")
                if (case := GhostCase.model_validate_json(raw)).organization_id == organization_id]

    def _update_reproduction(self, hunt: Hunt, candidate):
        matching = [c for c in hunt.candidates if c.phase == "reproduce" and c.controls == candidate.controls
                    and c.seed == candidate.seed and c.trial_id]
        baseline = next((c for c in hunt.candidates if c.phase != "reproduce" and c.controls == candidate.controls
                         and c.seed == candidate.seed and c.trial_id), None)
        if not baseline:
            return
        for case_id in hunt.case_ids:
            case = self.case(case_id)
            if case and case.baseline_trial_id == baseline.trial_id:
                case.reproduction = reproduction_result(case, [self.store.trials[c.trial_id] for c in matching])
                self.store.put_domain("ghost_case", case_id, case.model_dump_json())
