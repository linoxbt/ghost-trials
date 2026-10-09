"""Versioned, bounded physical recipes. Generated video is illustrative, not simulator state."""
from dataclasses import asdict, dataclass
import math
import random


@dataclass(frozen=True)
class HazardRecipe:
    version: str
    kind: str
    seed: int
    onset_s: float
    duration_s: float
    offset_m: tuple[float, float, float]
    velocity_m_s: tuple[float, float, float]
    box_size_m: tuple[float, float, float] = (0.3, 0.3, 0.3)
    mass_kg: float = 2.0
    reaction_action_delta: float = 0.15
    friction_coefficient: float | None = None

    def to_dict(self):
        return asdict(self)


CONTROL_BOUNDS = {
    "onset_s": (0.5, 8.0, "s"),
    "obstacle_distance_m": (0.3, 2.0, "m"),
    "obstacle_lateral_m": (-0.8, 0.8, "m"),
    "obstacle_speed_m_s": (0.0, 2.0, "m/s"),
    "object_mass_kg": (0.2, 10.0, "kg"),
    "friction_coefficient": (0.05, 0.8, "coefficient"),
}


def supported_controls(kind: str, backend: str) -> dict:
    if kind == "surface_instability":
        if backend != "gear_sonic_sim":
            raise ValueError("Reduced traction is supported only by gear_sonic_sim")
        names = ("onset_s", "friction_coefficient")
    elif kind in {"falling_object", "path_obstruction"} and backend in {"gear_sonic_sim", "isaac_arena_gr00t"}:
        names = ("onset_s", "obstacle_distance_m", "obstacle_lateral_m", "obstacle_speed_m_s", "object_mass_kg")
    else:
        raise ValueError(f"Unsupported hazard/backend combination: {kind}/{backend}")
    return {name: CONTROL_BOUNDS[name] for name in names}


def parameterize_hazard(scenario: dict, controls: dict, backend: str) -> HazardRecipe:
    """Compile only controls wired to the selected simulator, with explicit physical bounds."""
    kind = scenario["structured_description"]["hazard_type"]
    allowed = supported_controls(kind, backend)
    if set(controls) - set(allowed):
        raise ValueError(f"Unsupported simulator parameters: {sorted(set(controls) - set(allowed))}")
    for name, value in controls.items():
        lo, hi, _ = allowed[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{name} must be finite and within [{lo}, {hi}]")
    base = _default_hazard(scenario)
    data = base.to_dict()
    data["onset_s"] = float(controls.get("onset_s", base.onset_s))
    if kind == "surface_instability":
        data["friction_coefficient"] = float(controls.get("friction_coefficient", base.friction_coefficient))
    else:
        data["offset_m"] = (
            float(controls.get("obstacle_distance_m", base.offset_m[0])),
            float(controls.get("obstacle_lateral_m", base.offset_m[1])), base.offset_m[2],
        )
        data["velocity_m_s"] = (-float(controls.get("obstacle_speed_m_s", -base.velocity_m_s[0])), 0.0, 0.0)
        data["mass_kg"] = float(controls.get("object_mass_kg", base.mass_kg))
    return HazardRecipe(**data)


def _default_hazard(scenario: dict) -> HazardRecipe:
    kind = scenario["structured_description"]["hazard_type"]
    if kind not in {"falling_object", "path_obstruction", "surface_instability"}:
        raise ValueError(f"Unsupported executable hazard {kind!r}; available: falling_object, path_obstruction, surface_instability")
    seed = scenario["seed"]
    rng = random.Random(seed)
    side = rng.uniform(-0.25, 0.25)
    speed = {"low": 0.3, "medium": 0.6, "high": 0.9}[scenario["severity_tag"]]
    if kind == "surface_instability":
        return HazardRecipe(version="warehouse-traction-v1", kind=kind, seed=seed,
                            onset_s=3.0, duration_s=10.0, offset_m=(0, 0, 0), velocity_m_s=(0, 0, 0),
                            friction_coefficient={"low": .4, "medium": .2, "high": .05}[scenario["severity_tag"]])
    return HazardRecipe(
        version="warehouse-box-v1", kind=kind, seed=seed,
        onset_s=3.0, duration_s=10.0,
        offset_m=(0.8, side, 1.0 if kind == "falling_object" else -0.45),
        velocity_m_s=(-speed, 0.0, 0.0),
    )


def compile_hazard(scenario: dict) -> HazardRecipe:
    """Reject tampered, unbounded, or unsupported explicit recipes before execution."""
    base = _default_hazard(scenario)
    supplied = scenario.get("execution_recipe")
    if supplied is None:
        return base
    if not isinstance(supplied, dict) or set(supplied) != set(base.to_dict()):
        raise ValueError("Explicit hazard recipe must contain exactly the versioned recipe fields")
    if type(supplied["seed"]) is not int or any(
        isinstance(supplied[name], bool) or not isinstance(supplied[name], (int, float)) or not math.isfinite(supplied[name])
        for name in ("onset_s", "duration_s", "mass_kg", "reaction_action_delta")
    ):
        raise ValueError("Explicit recipe contains invalid numeric fields")
    if supplied["kind"] != base.kind or supplied["version"] != base.version or supplied["seed"] != base.seed:
        raise ValueError("Explicit recipe identity differs from scenario")
    if (supplied["duration_s"] != base.duration_s or tuple(supplied["box_size_m"]) != base.box_size_m
            or supplied["reaction_action_delta"] != base.reaction_action_delta):
        raise ValueError("Explicit recipe changes an unsupported control")
    if base.kind == "surface_instability":
        if (tuple(supplied["offset_m"]) != base.offset_m or tuple(supplied["velocity_m_s"]) != base.velocity_m_s
                or supplied["mass_kg"] != base.mass_kg):
            raise ValueError("Reduced-traction recipe changes an unsupported control")
        controls = {"onset_s": supplied["onset_s"], "friction_coefficient": supplied["friction_coefficient"]}
        backend = "gear_sonic_sim"
    else:
        offset, velocity = supplied["offset_m"], supplied["velocity_m_s"]
        if not isinstance(offset, (list, tuple)) or len(offset) != 3 or not isinstance(velocity, (list, tuple)) or len(velocity) != 3:
            raise ValueError("Invalid obstacle vector")
        if offset[2] != base.offset_m[2] or tuple(velocity[1:]) != (0.0, 0.0) or supplied["friction_coefficient"] is not None:
            raise ValueError("Explicit recipe changes an unsupported control")
        controls = {"onset_s": supplied["onset_s"], "obstacle_distance_m": offset[0], "obstacle_lateral_m": offset[1], "obstacle_speed_m_s": -velocity[0], "object_mass_kg": supplied["mass_kg"]}
        backend = "gear_sonic_sim"
    expected = parameterize_hazard({**scenario, "execution_recipe": None}, controls, backend)
    if expected.to_dict() != {**supplied, "offset_m": tuple(supplied["offset_m"]), "velocity_m_s": tuple(supplied["velocity_m_s"]), "box_size_m": tuple(supplied["box_size_m"])}:
        raise ValueError("Explicit recipe failed canonical validation")
    return expected
