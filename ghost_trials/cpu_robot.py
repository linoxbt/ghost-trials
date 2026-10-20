"""Headless CPU MuJoCo gantry-arm object-positioning experiment.

The artifact trajectory is sampled from mjData after real mj_step calls. It is
not a camera recording, physical robot observation, or a GR00T/SONIC policy.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import re
import time
import sys
from dataclasses import dataclass
from pathlib import Path

from .adapters import ScenarioGenerator, Simulator, TrialJudge
from .models import JudgeResult, Scenario, ScoreCategory, Severity, StructuredDescription, TrialMetrics, EvidenceEvent


TASK = "position a block with gantry arm"
ENVIRONMENT = "CPU MuJoCo tabletop"
ROBOT_ID = "ghost-gantry-xy-v1"
BACKEND = "mujoco_cpu"
HAZARD = "object_positioning"
CONTROL_BOUNDS = {
    "object_mass_kg": (0.05, 1.0, "kg"),
    "surface_friction": (0.1, 1.2, "coefficient"),
    "object_position_x_m": (0.35, 0.5, "m"),
    "controller_delay_s": (0.0, 1.2, "s"),
}
DEFAULTS = {"object_mass_kg": 0.15, "surface_friction": 0.3,
            "object_position_x_m": 0.4, "controller_delay_s": 0.0}


def controller_source_digest() -> str:
    """Pin executable physics/controller code in addition to controller parameters."""
    root = Path(__file__).resolve().parent
    checksum = hashlib.sha256()
    for name in ("cpu_robot.py", "cpu_worker.py"):
        checksum.update(name.encode())
        checksum.update((root / name).read_bytes())
    return checksum.hexdigest()


def initial_block_y(seed: int) -> float:
    """Seeded millimetre-scale pose perturbation, replayed exactly with the recipe."""
    return round(random.Random(seed).uniform(-0.003, 0.003), 7)


@dataclass(frozen=True)
class Controller:
    name: str
    speed_m_s: float
    target_x_m: float
    version: str = "1"

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()

    def command(self, now: float, object_x: float, pusher_x: float, object_vx: float) -> float:
        return min(self.target_x_m, 0.1 + self.speed_m_s * now)


@dataclass(frozen=True)
class NeuralController:
    name: str
    version: str
    layers: tuple
    digest: str

    def command(self, now: float, object_x: float, pusher_x: float, object_vx: float) -> float:
        values = [now / 3.0, object_x, pusher_x, object_vx]
        for index, layer in enumerate(self.layers):
            weights, biases = layer
            values = [sum(w * x for w, x in zip(row, values)) + bias for row, bias in zip(weights, biases)]
            if index < len(self.layers) - 1:
                values = [math.tanh(value) for value in values]
        z = max(-30.0, min(30.0, values[0]))
        return 0.1 + 0.8 / (1.0 + math.exp(-z))


CONTROLLERS = {
    "gantry-push-v1": Controller("gantry-push-v1", 0.32, 0.69),
    "gantry-push-v2": Controller("gantry-push-v2", 0.52, 0.77),
}


def _policy_dir() -> Path:
    return Path(os.environ.get("GHOST_CPU_POLICY_DIR") or Path(__file__).resolve().parent / "policies" / "cpu")


def _neural_controller(name: str) -> NeuralController:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ValueError("Invalid CPU policy identifier")
    path = _policy_dir() / f"{name}.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 131_072:
        raise ValueError(f"Unsupported CPU policy {name!r}; register a bounded JSON checkpoint")
    content = path.read_bytes()
    raw = json.loads(content)
    if not isinstance(raw, dict) or set(raw) != {"schema", "robot_model", "version", "layers"}:
        raise ValueError("Invalid neural policy schema")
    if (raw["schema"] != "ghost-cpu-mlp-v1" or raw["robot_model"] != ROBOT_ID
            or not isinstance(raw["version"], str) or not 1 <= len(raw["version"]) <= 64):
        raise ValueError("Neural policy has incompatible observation/action contract")
    layers = raw["layers"]
    if not isinstance(layers, list) or not 1 <= len(layers) <= 3:
        raise ValueError("Neural policy must have one to three layers")
    previous = 4
    parsed = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict) or set(layer) != {"weights", "bias"}:
            raise ValueError("Invalid neural layer")
        weights, bias = layer["weights"], layer["bias"]
        if not isinstance(weights, list) or not isinstance(bias, list) or not 1 <= len(weights) <= 16 or len(weights) != len(bias):
            raise ValueError("Invalid neural layer shape")
        if index == len(layers) - 1 and len(weights) != 1:
            raise ValueError("Neural policy must output one bounded actuator target")
        if any(not isinstance(row, list) or len(row) != previous for row in weights):
            raise ValueError("Invalid neural weight shape")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 100
               for row in weights for v in row) or any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or abs(v) > 100 for v in bias):
            raise ValueError("Neural policy weights must be bounded finite numbers")
        parsed.append((tuple(tuple(float(v) for v in row) for row in weights), tuple(float(v) for v in bias)))
        previous = len(weights)
    return NeuralController(name, raw["version"], tuple(parsed), "sha256:" + hashlib.sha256(content).hexdigest())


def available_policies() -> list[str]:
    names = list(CONTROLLERS)
    directory = _policy_dir()
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            if path.stem not in CONTROLLERS:
                try:
                    _neural_controller(path.stem)
                except (ValueError, OSError, json.JSONDecodeError):
                    continue
                names.append(path.stem)
    return names


def controller(name: str) -> Controller | NeuralController:
    return CONTROLLERS[name] if name in CONTROLLERS else _neural_controller(name)


def recipe(seed: int, controls: dict | None = None) -> dict:
    controls = controls or {}
    if set(controls) - set(CONTROL_BOUNDS):
        raise ValueError(f"Unsupported CPU physics controls: {sorted(set(controls) - set(CONTROL_BOUNDS))}")
    values = DEFAULTS | controls
    for name, value in values.items():
        lo, hi, _ = CONTROL_BOUNDS[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{name} outside executable bounds [{lo}, {hi}]")
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise ValueError("Invalid CPU experiment seed")
    return {"version": "gantry-tabletop-v1", "kind": HAZARD, "seed": seed,
            **{name: float(value) for name, value in values.items()}}


def validate_recipe(value: dict, seed: int) -> dict:
    if not isinstance(value, dict) or set(value) != {"version", "kind", "seed", *CONTROL_BOUNDS}:
        raise ValueError("CPU recipe must contain exactly the supported fields")
    if value["version"] != "gantry-tabletop-v1" or value["kind"] != HAZARD or value["seed"] != seed:
        raise ValueError("CPU recipe identity differs from scenario")
    canonical = recipe(seed, {name: value[name] for name in CONTROL_BOUNDS})
    if canonical != value:
        raise ValueError("CPU recipe is not canonical")
    return canonical


def mjcf(config: dict) -> str:
    mass = config["object_mass_kg"]
    friction = config["surface_friction"]
    x = config["object_position_x_m"]
    y = initial_block_y(config["seed"])
    return f"""<mujoco model="{ROBOT_ID}">
  <option timestep="0.005" gravity="0 0 -9.81" integrator="implicitfast"/>
  <default><joint damping="2"/><geom condim="3" solref="0.004 1"/></default>
  <worldbody>
    <geom name="table" type="plane" size="1 1 0.1" friction="{friction} 0.005 0.0001"/>
    <body name="gantry" pos="0 0 0.075">
      <inertial pos="0 0 0" mass="0.4" diaginertia="0.001 0.001 0.001"/>
      <joint name="axis_x" type="slide" axis="1 0 0" limited="true" range="0 0.9"/>
      <body name="cross_slide">
        <joint name="axis_y" type="slide" axis="0 1 0" limited="true" range="-0.25 0.25"/>
        <geom name="pusher" type="sphere" size="0.034" mass="0.6" friction="0.8 0.005 0.0001"/>
      </body>
    </body>
    <body name="block" pos="{x} {y} 0.04">
      <freejoint/>
      <geom name="block_geom" type="box" size="0.04 0.04 0.04" mass="{mass}" friction="{friction} 0.005 0.0001"/>
    </body>
  </worldbody>
  <actuator>
    <position name="move_x" joint="axis_x" kp="180" dampratio="1" forcelimited="true" forcerange="-8 8" ctrlrange="0 0.9" ctrllimited="true"/>
    <position name="move_y" joint="axis_y" kp="180" dampratio="1" forcelimited="true" forcerange="-8 8" ctrlrange="-0.25 0.25" ctrllimited="true"/>
  </actuator>
</mujoco>"""


def execute(config: dict, policy_id: str) -> tuple[dict, list[dict], str]:
    import mujoco
    import numpy as np
    validate_recipe(config, config["seed"])
    policy = controller(policy_id)
    model = mujoco.MjModel.from_xml_string(mjcf(config))
    data = mujoco.MjData(model)
    data.qpos[0] = 0.1
    mujoco.mj_forward(model, data)
    steps = 600  # exactly 3 simulated seconds, independent of wall-clock speed
    rows = []
    start = time.perf_counter()
    max_force = 0.0
    collision_count = 0
    limit_count = 0
    contact_first = None
    table_touching_before = False
    max_tracking_error = 0.0
    max_block_tilt = 0.0
    policy_time_s = 0.0
    for step in range(steps + 1):
        now = float(data.time)
        policy_started = time.perf_counter()
        desired = 0.1 if now < config["controller_delay_s"] else policy.command(
            now - config["controller_delay_s"], float(data.body("block").xpos[0]),
            float(data.geom("pusher").xpos[0]), float(data.qvel[2]))
        if not math.isfinite(desired) or not 0.0 <= desired <= 0.9:
            raise ValueError("CPU controller returned an invalid actuator target")
        policy_time_s += time.perf_counter() - policy_started
        data.ctrl[:] = (desired, 0.0)
        if step < steps:
            mujoco.mj_step(model, data)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise RuntimeError("MuJoCo produced non-finite robot state; no task outcome")
        force = 0.0
        touching = False
        table_touching = False
        for i in range(data.ncon):
            contact = data.contact[i]
            names = {model.geom(c).name for c in (contact.geom1, contact.geom2)}
            if names == {"pusher", "block_geom"}:
                touching = True
                value = np.zeros(6)
                mujoco.mj_contactForce(model, data, i, value)
                force = max(force, float(np.linalg.norm(value[:3])))
            elif names == {"pusher", "table"}:
                table_touching = True
        if table_touching and not table_touching_before:
            collision_count += 1
        table_touching_before = table_touching
        if touching and contact_first is None:
            contact_first = float(data.time)
        max_force = max(max_force, force)
        xjoint, yjoint = map(float, data.qpos[:2])
        tracking_error = abs(desired - xjoint)
        max_tracking_error = max(max_tracking_error, tracking_error)
        block_tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(data.body("block").xmat[8])))))
        max_block_tilt = max(max_block_tilt, block_tilt)
        limit_violation = not 0 <= xjoint <= 0.9 or not -0.25 <= yjoint <= 0.25
        if limit_violation:
            limit_count += 1
        if step % 5 == 0 or step == steps:
            rows.append({"timestamp_ms": round(float(data.time) * 1000, 3),
                         "joint_positions_m": [round(xjoint, 6), round(yjoint, 6)],
                         "joint_velocities_m_s": [round(float(v), 6) for v in data.qvel[:2]],
                         "pusher_position_m": [round(float(v), 6) for v in data.geom("pusher").xpos],
                         "object_position_m": [round(float(v), 6) for v in data.body("block").xpos],
                         "object_velocity_m_s": [round(float(v), 6) for v in data.qvel[2:5]],
                         "controller_target_x_m": round(desired, 6),
                         "pusher_block_contact": touching, "contact_force_n": round(force, 6),
                         "joint_limit_violation": limit_violation,
                         "controller_tracking_error_m": round(tracking_error, 6),
                         "block_tilt_deg": round(block_tilt, 6)})
    elapsed = time.perf_counter() - start
    initial_x = config["object_position_x_m"]
    final_x = float(data.body("block").xpos[0])
    success = 0.64 <= final_x <= 0.86 and abs(float(data.body("block").xpos[1])) <= 0.12
    result = {"robot_model": ROBOT_ID, "policy_id": policy_id, "policy_version": policy.version,
              "policy_digest": policy.digest, "controller_source_digest": controller_source_digest(),
              "simulator": "MuJoCo", "simulator_version": mujoco.__version__,
              "simulation_duration_s": round(float(data.time), 6), "wall_duration_s": round(elapsed, 6),
              "object_initial_x_m": initial_x, "object_final_x_m": round(final_x, 6),
              "object_displacement_m": round(final_x - initial_x, 6),
              "object_target_error_m": round(abs(final_x - 0.75), 6),
              "task_completed": success, "max_contact_force_n": round(max_force, 6),
              "pusher_object_contact_count": sum(row["pusher_block_contact"] for row in rows),
              "pusher_table_collision_count": collision_count,
              "joint_limit_violation_count": limit_count,
              "max_joint_tracking_error_m": round(max_tracking_error, 6),
              "max_block_tilt_deg": round(max_block_tilt, 6),
              "controller_execution_time_ms": round(policy_time_s * 1000, 6),
              "controller_first_contact_s": round(contact_first, 6) if contact_first is not None else None,
              "trace_samples": len(rows), "measurement_basis": "MuJoCo mjData sampled every 5 physics steps; contact force computed with mj_contactForce. Contact count is sampled, not a continuous contact duration; table collision count is contact-onset events."}
    return result, rows, mujoco.__version__


class CpuScenarioGenerator(ScenarioGenerator):
    async def generate(self, scenario_id: str, prompt: str, severity: Severity | None, seed: int) -> Scenario:
        if "block" not in prompt.lower() and "object" not in prompt.lower():
            raise ValueError("CPU backend supports only tabletop block positioning")
        return Scenario(scenario_id=scenario_id, prompt=prompt.strip(), seed=seed,
                        severity_tag=severity or Severity.MEDIUM,
                        structured_description=StructuredDescription(objects=["gantry arm", "block", "table"],
                            hazard_type=HAZARD, severity=severity or Severity.MEDIUM,
                            expected_safe_behavior="Position the block center between x=0.64 and 0.86 m within 3 simulated seconds."),
                        generation_provenance={"provider": "deterministic_cpu_recipe", "is_robot_execution_evidence": False})


class CpuMujocoSimulator(Simulator):
    accepts_trial = True
    def __init__(self):
        self.last_result = None

    async def run(self, scenario: Scenario, trial=None) -> TrialMetrics:
        if trial is None:
            raise ValueError("CPU simulator requires a trial and controller identity")
        config = validate_recipe(scenario.execution_recipe, scenario.seed)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ghost_trials.cpu_worker", stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            output, error = await asyncio.wait_for(process.communicate(
                json.dumps({"recipe": config, "policy_id": trial.policy_name}).encode()), timeout=20)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("CPU physics worker exceeded 20 seconds; no outcome recorded")
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        if process.returncode or len(output) > 2_000_000:
            raise RuntimeError(f"CPU physics worker failed ({process.returncode}); no outcome recorded")
        payload = json.loads(output)
        result, rows, version = payload["summary"], payload["trace"], payload["simulator_version"]
        self.last_result = {"summary": result, "trace": rows, "recipe": config}
        events = [EvidenceEvent(kind="hazard_onset", timestamp_ms=0, description="Block-positioning task begins")]
        if result["controller_first_contact_s"] is not None:
            events.append(EvidenceEvent(kind="reaction", timestamp_ms=result["controller_first_contact_s"] * 1000,
                                        description="Pusher first contacted block"))
        events.append(EvidenceEvent(kind="outcome", timestamp_ms=result["simulation_duration_s"] * 1000,
                                    description="Block reached target band" if result["task_completed"] else "Block did not reach target band"))
        return TrialMetrics(time_to_react_ms=round(result["controller_first_contact_s"] * 1000) if result["controller_first_contact_s"] is not None else None,
                            min_clearance_m=None, task_completed=result["task_completed"],
                            fall_or_collision=result["pusher_table_collision_count"] > 0,
                            observation_window_ms=round(result["simulation_duration_s"] * 1000),
                            simulator_version=f"MuJoCo {version}; {ROBOT_ID}",
                            policy_checkpoint_digest=result["policy_digest"], evidence_origin="simulator",
                            measurements_are_proxies=False, metric_basis=result["measurement_basis"],
                            events=events, robot_metrics=result)


class CpuMeasuredJudge(TrialJudge):
    async def judge(self, scenario: Scenario, metrics: TrialMetrics) -> JudgeResult:
        if scenario.structured_description.hazard_type != HAZARD or not metrics.robot_metrics:
            return JudgeResult(score_category=ScoreCategory.INSUFFICIENT, confidence=0,
                               reasoning_trace="CPU task evidence is unavailable.", tier_used="cpu-measured-rubric-v1")
        summary = metrics.robot_metrics
        category = ScoreCategory.AVOIDED if summary["task_completed"] else ScoreCategory.FAILED
        return JudgeResult(score_category=category, confidence=1.0,
                           reasoning_trace=f"Measured block center x={summary['object_final_x_m']:.3f} m after {summary['simulation_duration_s']:.3f} simulated seconds; target band is 0.64–0.86 m. Controller {summary['policy_id']} executed in MuJoCo. This is a task outcome, not a safety certificate.",
                           tier_used="cpu-measured-rubric-v1")
