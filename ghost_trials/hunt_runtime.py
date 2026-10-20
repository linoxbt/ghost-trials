"""Durable, admission-controlled Hunt orchestration over the existing trial queue."""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
import time
import random
from pathlib import Path

from .adapters import ExecutionBlocked
from .hunt import (GhostCase, Hunt, HuntObjective, HuntPlanner, HuntStatus, PolicyVersion, TrialCandidate,
                   SearchSpace, case_from_trial, default_space, empirical_boundary,
                   observed_outcome, reproduction_result)
from .models import ScenarioCreate, TrialStatus
from .agent_verification import (AgentHunt, AgentHuntObjective, AgentSearchSpace, AgentTarget,
                                 AgentPolicy, AgentTrial, AgentGhostCase, AgentVerdict,
                                 TARGETS, OBJECTIVE_VARIANTS, OBJECTIVE_ASSERTIONS,
                                 execute_reference, make_scenario, verify_trial, reference_source_digest)
from .retained_evidence import reporting_trial
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
    def __init__(self, store, pipeline, settings, admission, admission_lock, agent_admission=None):
        self.store, self.pipeline, self.settings = store, pipeline, settings
        self.admission, self.admission_lock = admission, admission_lock
        self.agent_admission = agent_admission or admission
        self.tasks: dict[str, asyncio.Task] = {}
        self.agent_slots = asyncio.Semaphore(2)

    def get(self, hunt_id: str) -> Hunt | AgentHunt | None:
        raw = self.store.get_domain("hunt", hunt_id)
        if not raw:
            return None
        return (AgentHunt if json.loads(raw).get("domain") == "ai_agent" else Hunt).model_validate_json(raw)

    def list(self, organization_id: str) -> list[Hunt | AgentHunt]:
        return [(AgentHunt if json.loads(raw).get("domain") == "ai_agent" else Hunt).model_validate_json(raw)
                for raw in self.store.list_domain_for_org("hunt", organization_id)]

    def save(self, hunt: Hunt | AgentHunt):
        from .models import utc_now
        hunt.updated_at = time.time() if isinstance(hunt, AgentHunt) else utc_now().isoformat()
        self.store.put_domain("hunt", hunt.hunt_id, hunt.model_dump_json())

    def create_agent(self, organization_id: str, target_id: str, objective: AgentHuntObjective,
                     max_trials: int, strategy: str, policy: AgentPolicy | None = None,
                     search_space: AgentSearchSpace | None = None, max_wall_seconds: int = 60) -> AgentHunt:
        target = AgentTarget(target_id=target_id, organization_id=organization_id,
                             name=target_id, version=TARGETS[target_id],
                             source_digest=reference_source_digest()) if target_id in TARGETS else None
        if target is None:
            raise ValueError("Only bundled reference agents are supported; external code execution is blocked")
        permitted = OBJECTIVE_VARIANTS[objective.verification_objective]
        space = search_space or AgentSearchSpace(attack_variants=sorted(permitted))
        if not set(space.attack_variants) <= permitted:
            raise ValueError("Candidate variants must match the selected verification objective")
        hunt = AgentHunt(hunt_id=f"hunt_{uuid.uuid4().hex[:12]}", organization_id=organization_id,
                         objective=objective, target=target, policy=policy or AgentPolicy(),
                         search_space=space, strategy=strategy,
                         max_trials=max_trials, max_wall_seconds=max_wall_seconds)
        self.store.put_domain("agent_target", target.target_id + ":" + organization_id, target.model_dump_json())
        self.save(hunt)
        return hunt

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
            hunt = (AgentHunt if json.loads(raw).get("domain") == "ai_agent" else Hunt).model_validate_json(raw)
            if hunt.status in {HuntStatus.QUEUED, HuntStatus.RUNNING}:
                hunt.status = HuntStatus.INTERRUPTED
                hunt.provider_errors.append("Hunt interrupted; inspect in-flight job before explicit resume")
                self.save(hunt)

    async def run(self, hunt_id: str, subject: str):
        hunt = self.get(hunt_id)
        if not hunt or hunt.status not in {HuntStatus.QUEUED, HuntStatus.INTERRUPTED}:
            return
        if isinstance(hunt, AgentHunt):
            await self.run_agent(hunt, subject)
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
                observed_trial = await asyncio.to_thread(reporting_trial, trial,
                    self.store.scenarios[trial.scenario_id], self.settings.ghost_artifact_root)
                candidate.outcome, candidate.observation = observed_outcome(
                    observed_trial, self.store.scenarios[trial.scenario_id], allow_synthetic_fixture=self.settings.ghost_mode == "local" and all(
                        p == "local" for p in (self.settings.ghost_scenario_provider,
                                               self.settings.ghost_simulator_provider, self.settings.ghost_judge_provider)))
                from .evaluation import evidence_class, evidence_report
                candidate.evidence_class = evidence_class(observed_trial)
                candidate.simulator_version = trial.metrics.simulator_version if trial.metrics else None
                if candidate.evidence_class == "artifact_validated_simulation":
                    missing = evidence_report(observed_trial, self.store.scenarios[trial.scenario_id])["missing_evidence"]
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

    def case(self, case_id: str) -> GhostCase | AgentGhostCase | None:
        raw = self.store.get_domain("ghost_case", case_id)
        if not raw:
            return None
        case = (AgentGhostCase if json.loads(raw).get("domain") == "ai_agent" else GhostCase).model_validate_json(raw)
        return self._checked_agent_case(case) if isinstance(case, AgentGhostCase) else self._checked_physical_case(self._with_manual_replays(case))

    def cases(self, organization_id: str) -> list[GhostCase | AgentGhostCase]:
        replay_rows = [json.loads(raw) for raw in self.store.list_domain_for_org("case_replay", organization_id)]
        trial_rows = list(self.store.trials.values())
        return [self._checked_agent_case(case) if isinstance(case, AgentGhostCase) else self._checked_physical_case(
                    self._with_manual_replays(case, replay_rows, trial_rows))
                for raw in self.store.list_domain_for_org("ghost_case", organization_id)
                if (case := (AgentGhostCase if json.loads(raw).get("domain") == "ai_agent" else GhostCase).model_validate_json(raw))]

    def _checked_physical_case(self, case: GhostCase) -> GhostCase:
        """Recheck retained baseline bytes; a saved verification flag is not proof of current integrity."""
        trial = self.store.trials.get(case.baseline_trial_id)
        try:
            case.evidence_verification = self._verify_physical_bundle(case, trial, baseline=True)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            case.evidence_verification = {"status": "invalid_retained_evidence"}
            case.reproduction.status = "incomplete" if case.reproduction.attempts else "unattempted"
        return case

    def _verify_physical_bundle(self, case: GhostCase, trial, *, baseline: bool = False) -> dict:
        if not trial or not trial.metrics or trial.organization_id != case.organization_id:
            raise ValueError("Saved trial is unavailable or outside case organization")
        root = Path(self.settings.ghost_artifact_root).resolve()
        directory = (root / "trials" / trial.trial_id).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Unsafe retained artifact path")
        if trial.metrics.policy_checkpoint_digest != case.policy.checkpoint_digest:
            raise ValueError("Saved trial differs from case checkpoint")
        if baseline and trial.metrics.artifact_manifest != case.artifact_manifest:
            raise ValueError("Saved trial differs from case manifest")
        if case.policy.embodiment == "GHOST_GANTRY_XY":
            from .cpu_evidence import verify_cpu_bundle
            verification = verify_cpu_bundle(directory, case.policy.checkpoint_digest)
            manifest = json.loads((directory / "manifest.json").read_text())
            summary = json.loads((directory / "summary.json").read_text())
            if (manifest != trial.metrics.artifact_manifest or
                    json.loads((directory / "recipe.json").read_text()) != case.execution_recipe or
                    summary != trial.metrics.robot_metrics or
                    baseline and summary != case.measured_metrics.get("robot_metrics")):
                raise ValueError("Retained CPU evidence differs from trial or case")
        else:
            from .independent_validation import verify_bundle
            verification = verify_bundle(directory, case.policy.checkpoint_digest)
            manifest = json.loads((directory / "result.json").read_text())["artifacts"]
            if manifest != trial.metrics.artifact_manifest or baseline and manifest != case.artifact_manifest:
                raise ValueError("Retained worker manifest differs from saved trial or case")
        return verification

    def _with_manual_replays(self, case: GhostCase, rows=None, trial_rows=None) -> GhostCase:
        rows = rows if rows is not None else [json.loads(raw) for raw in self.store.list_domain_for_org("case_replay", case.organization_id)]
        trial_rows = trial_rows if trial_rows is not None else self.store.trials.values()
        ids = list(dict.fromkeys(case.reproduction.attempts +
                                  [row["trial_id"] for row in rows if row.get("case_id") == case.case_id] +
                                  [trial.trial_id for trial in trial_rows
                                   if trial.replay_of == case.baseline_trial_id
                                   and trial.organization_id == case.organization_id
                                   and trial.policy_name == case.policy.name]))
        attempts = []
        invalid = False
        from .evaluation import evidence_report
        for trial_id in ids:
            trial = self.store.trials.get(trial_id)
            if trial is None or (trial.replay_of != case.baseline_trial_id and trial_id not in case.reproduction.attempts):
                invalid = True
                continue
            scenario = self.store.scenarios.get(trial.scenario_id)
            if (not scenario or scenario.execution_recipe != case.execution_recipe or
                    not trial.metrics or trial.metrics.policy_checkpoint_digest != case.policy.checkpoint_digest or
                    evidence_report(trial, scenario)["missing_evidence"]):
                invalid = True
                continue
            try:
                self._verify_physical_bundle(case, trial)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                invalid = True
                continue
            attempts.append(trial)
        case.reproduction = reproduction_result(case, attempts)
        if invalid:
            case.reproduction.attempts = ids
            case.reproduction.status = "incomplete"
        return case

    def _checked_agent_case(self, case):
        if isinstance(case, AgentGhostCase):
            baseline = self.agent_trial(case.baseline_trial_id)
            valid = bool(baseline and baseline.organization_id == case.organization_id
                         and baseline.evidence_sha256 == case.evidence_sha256 and verify_trial(baseline))
            legacy = bool(baseline and (not baseline.target.source_digest or not baseline.runtime_id or
                                        any(a.version != "agent-oracle-v2" for a in baseline.assertions)))
            case.evidence_verification = {"status": "verified" if valid else
                                          "legacy_unverified" if legacy else "invalid",
                                          "oracle_version": baseline.assertions[0].version
                                              if baseline and baseline.assertions else "unknown"}
            case.reproduction_status = (self._agent_reproduction_status(case) if valid else
                                        "incomplete" if case.reproduction_trial_ids else "unattempted")
        return case

    def agent_trial(self, trial_id: str) -> AgentTrial | None:
        raw = self.store.get_domain("agent_trial", trial_id)
        return AgentTrial.model_validate_json(raw) if raw else None

    def _agent_candidate(self, hunt: AgentHunt) -> TrialCandidate | None:
        if len(hunt.candidates) >= hunt.max_trials:
            return None
        n = len(hunt.candidates) + 1
        failures = [c for c in hunt.candidates if c.outcome == "failure"]
        if hunt.strategy == "adaptive" and failures:
            anchor = failures[0]
            repeats = [c for c in hunt.candidates if c.phase == "reproduce" and c.controls == anchor.controls]
            if len(repeats) < 2:
                return TrialCandidate(sequence=n, phase="reproduce", controls=anchor.controls.copy(), seed=anchor.seed)
            variant = int(anchor.controls["attack_variant"])
            # Pressure changes only variant 2. Never count an unchanged
            # effective scenario as a new mutation or coverage point.
            options = ([(variant, p) for p in hunt.search_space.pressures if variant == 2] +
                       [(v, hunt.search_space.pressures[0]) for v in hunt.search_space.attack_variants if v != variant])
            tried = {(int(c.controls["attack_variant"]), int(c.controls["pressure"]))
                     for c in hunt.candidates if c.phase != "reproduce"}
            next_option = next(((v, p) for v, p in options if (v, p) not in tried), None)
            if next_option is None:
                return None
            variant, pressure = next_option
            phase = "mutate"
        else:
            variants = [v for v in (0, 2, 1, 3, 4) if v in hunt.search_space.attack_variants]
            options = [(v, p) for v in variants for p in
                       (hunt.search_space.pressures if v == 2 else hunt.search_space.pressures[:1])]
            if hunt.strategy == "random":
                random.Random(hunt.hunt_id).shuffle(options)
            tried = {(int(c.controls["attack_variant"]), int(c.controls["pressure"]))
                     for c in hunt.candidates if c.phase != "reproduce"}
            next_option = next(((v, p) for v, p in options if (v, p) not in tried), None)
            if next_option is None:
                return None
            variant, pressure = next_option
            phase = "explore"
        seed = int(hashlib.sha256(f"{hunt.hunt_id}:{n}".encode()).hexdigest()[:8], 16) % 2_147_483_647
        if phase in {"reproduce", "mutate"}:
            seed = anchor.seed
        return TrialCandidate(sequence=n, phase=phase,
                              controls={"attack_variant": float(variant), "pressure": float(pressure)}, seed=seed)

    async def run_agent(self, hunt: AgentHunt, subject: str):
        hunt.status = HuntStatus.RUNNING
        self.save(hunt)
        deadline = time.monotonic() + hunt.max_wall_seconds
        try:
            while len(hunt.candidates) < hunt.max_trials and time.monotonic() < deadline:
                candidate = hunt.candidates[-1] if hunt.candidates and hunt.candidates[-1].outcome is None else self._agent_candidate(hunt)
                if candidate is None:
                    break
                if candidate not in hunt.candidates:
                    hunt.candidates.append(candidate)
                    self.save(hunt)
                trial_id = candidate.trial_id or f"atrial_{uuid.uuid4().hex[:12]}"
                candidate.trial_id = trial_id
                self.save(hunt)
                await self.admission_lock.acquire()
                try:
                    self.agent_admission()
                    if not self.store.get_domain("agent_reservation", trial_id):
                        today = int(time.time() // 86400)
                        used = sum(int(json.loads(raw)["at"] // 86400) == today
                                   for raw in self.store.list_domain("agent_reservation"))
                        if self.store.job_counts()["submitted_today"] + used >= self.settings.ghost_max_jobs_per_day:
                            raise ValueError("Daily execution budget exhausted")
                        self.store.put_domain("agent_reservation", trial_id, json.dumps({
                            "organization_id": hunt.organization_id, "hunt_id": hunt.hunt_id, "at": time.time()}))
                finally:
                    self.admission_lock.release()
                variant, pressure = int(candidate.controls["attack_variant"]), int(candidate.controls["pressure"])
                if variant not in hunt.search_space.attack_variants or pressure not in hunt.search_space.pressures:
                    raise ValueError("Persisted candidate exceeded the declared search space")
                scenario = make_scenario(variant, pressure, candidate.seed)
                trial = self.agent_trial(trial_id)
                if trial is None:
                    async with self.agent_slots:
                        trial = await asyncio.to_thread(execute_reference, hunt.target, hunt.policy, scenario,
                                                        hunt_id=hunt.hunt_id, trial_id=trial_id,
                                                        objective=hunt.objective.verification_objective,
                                                        timeout_s=min(3.0, max(.1, deadline - time.monotonic())))
                    self.store.put_domain("agent_trial", trial_id, trial.model_dump_json())
                    self.store.audit("agent_trial_completed", "operator", trial_id,
                                     organization_id=hunt.organization_id, subject=subject)
                if trial.status == AgentVerdict.EXECUTION_ERROR and verify_trial(trial):
                    candidate.outcome = "provider_error"
                    candidate.observation = trial.error
                    hunt.provider_errors.append(f"{trial_id}: {trial.error}")
                    hunt.status = HuntStatus.BLOCKED
                elif not verify_trial(trial):
                    candidate.outcome = "insufficient_evidence"
                    candidate.observation = "Evidence digest mismatch or invalid oracle record"
                    hunt.status = HuntStatus.BLOCKED
                elif trial.status == AgentVerdict.VERIFIED_FAILURE:
                    candidate.outcome = "failure"
                    candidate.observation = ", ".join(a.assertion_id for a in trial.assertions if not a.passed)
                    if candidate.phase != "reproduce":
                        case = AgentGhostCase(case_id=f"gcase_{uuid.uuid4().hex[:12]}", hunt_id=hunt.hunt_id,
                                              organization_id=hunt.organization_id, baseline_trial_id=trial_id,
                                              target=hunt.target, policy=hunt.policy,
                                              objective=hunt.objective.verification_objective, scenario=scenario,
                                              assertion_ids=[a.assertion_id for a in trial.assertions if not a.passed
                                                             and a.assertion_id in OBJECTIVE_ASSERTIONS[hunt.objective.verification_objective]],
                                              evidence_sha256=trial.evidence_sha256)
                        self.store.put_domain("ghost_case", case.case_id, case.model_dump_json())
                        hunt.case_ids.append(case.case_id)
                else:
                    candidate.outcome = "pass"
                    candidate.observation = "All deterministic assertions passed"
                if candidate.phase == "reproduce":
                    for case_id in hunt.case_ids:
                        case = self.case(case_id)
                        if isinstance(case, AgentGhostCase) and case.scenario == scenario:
                            self.record_agent_reproduction(case, trial)
                candidate.evidence_class = "validated_agent_trace" if verify_trial(trial) else "invalid"
                candidate.simulator_version = hunt.adapter_version
                self.save(hunt)
                if hunt.status == HuntStatus.BLOCKED:
                    return
            hunt.status = HuntStatus.COMPLETE if time.monotonic() < deadline else HuntStatus.INTERRUPTED
            if hunt.status == HuntStatus.INTERRUPTED:
                hunt.provider_errors.append("Hunt wall-time budget exhausted; no further trials executed")
            self.save(hunt)
        except asyncio.CancelledError:
            hunt.status = HuntStatus.INTERRUPTED
            self.save(hunt)
            raise
        except ValueError as exc:
            hunt.status = HuntStatus.BLOCKED
            hunt.provider_errors.append(str(exc) if str(exc) == "Daily execution budget exhausted"
                                        else "Agent Hunt stopped (ValueError); no policy failure inferred")
            self.save(hunt)
        except Exception as exc:
            hunt.status = HuntStatus.BLOCKED
            hunt.provider_errors.append(f"Agent Hunt stopped ({type(exc).__name__}); no policy failure inferred")
            self.save(hunt)

    def record_agent_reproduction(self, case: AgentGhostCase, trial: AgentTrial):
        if trial.trial_id not in case.reproduction_trial_ids:
            case.reproduction_trial_ids.append(trial.trial_id)
        case.reproduction_status = self._agent_reproduction_status(case)
        self.store.put_domain("ghost_case", case.case_id, case.model_dump_json())

    def _agent_reproduction_status(self, case: AgentGhostCase) -> str:
        if not case.reproduction_trial_ids:
            return "unattempted"
        attempts = [self.agent_trial(tid) for tid in case.reproduction_trial_ids]
        if any(not t or t.organization_id != case.organization_id or t.target != case.target or
               t.policy != case.policy or t.objective != case.objective or t.scenario != case.scenario or
               not verify_trial(t) for t in attempts):
            return "incomplete"
        statuses = [t.status for t in attempts]
        if len(statuses) < 2 or any(s not in {AgentVerdict.VERIFIED_FAILURE, AgentVerdict.VERIFIED_SUCCESS}
                                    for s in statuses):
            return "incomplete"
        if all(s == AgentVerdict.VERIFIED_FAILURE for s in statuses):
            return "reproducible"
        return "flaky" if AgentVerdict.VERIFIED_FAILURE in statuses else "not_reproduced"

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
