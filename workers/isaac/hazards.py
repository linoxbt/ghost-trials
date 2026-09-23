"""Versioned, bounded physical recipes. Generated video is illustrative, not simulator state."""
from dataclasses import asdict, dataclass
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


def compile_hazard(scenario: dict) -> HazardRecipe:
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
