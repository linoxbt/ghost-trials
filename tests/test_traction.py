import json

import pytest

from workers.isaac.hazards import compile_hazard
from workers.isaac.traction import GroundTraction
from workers.isaac.trial_runner import derive_metrics


def scenario():
    return {"seed": 42, "severity_tag": "high", "structured_description": {"hazard_type": "surface_instability"}}


def slide(mu, explicit_pair=False):
    mujoco = pytest.importorskip("mujoco")
    pair = '<contact><pair geom1="floor" geom2="slider" friction="1 1 .005 .0001 .0001"/></contact>' if explicit_pair else ''
    model = mujoco.MjModel.from_xml_string(f'''<mujoco><option timestep="0.001"/><worldbody>
      <geom name="floor" type="plane" size="5 5 .1" friction="1 .005 .0001"/>
      <body pos="0 0 .099"><freejoint/><geom name="slider" type="box" size=".1 .1 .1" mass="1" friction="1 .005 .0001"/></body>
      </worldbody>{pair}</mujoco>''')
    data = mujoco.MjData(model)
    for _ in range(300):
        mujoco.mj_step(model, data)
    traction = GroundTraction(model, mu)
    before = model.geom_friction.copy()
    traction.activate()
    data.qvel[0] = 1
    observations = []
    for _ in range(400):
        mujoco.mj_step(model, data)
        observations.append(traction.observe(data, {model.geom("slider").id}))
    distance = float(data.qpos[0])
    traction.restore()
    assert (model.geom_friction == before).all()
    coefficients = [r["effective_friction"] for r in observations if r["effective_friction"] is not None]
    assert coefficients and all(abs(v - mu) < 1e-6 for v in coefficients)
    assert any((r["contact_slip_speed_m_s"] or 0) > .1 for r in observations)
    return distance


@pytest.mark.parametrize("explicit_pair", [False, True])
def test_real_physics_low_friction_slides_further(explicit_pair):
    high = slide(.8, explicit_pair)
    low = slide(.05, explicit_pair)
    assert low > high * 2  # Real CPU physics experiment, not a robot-policy result.


def test_traction_telemetry_requires_effective_friction_and_has_no_clearance(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    rows = [{"timestamp_ms": t, "hazard_active": True, "policy_reacted": False, "clearance_m": None,
             "collision": False, "fall": False, "ground_contact_count": 2,
             "effective_friction": .05, "contact_slip_speed_m_s": speed}
            for t, speed in [(3000, .1), (3500, .3)]]
    path.write_text("\n".join(map(json.dumps, rows)))
    request = {"scenario": scenario(), "policy": {}}
    metrics = derive_metrics(path, request)
    assert metrics.min_clearance_m is None
    assert metrics.max_contact_slip_speed_m_s == .3 and metrics.effective_friction == .05
    assert not any(e.kind == "closest_approach" for e in metrics.events)
    rows[1]["effective_friction"] = .8
    path.write_text("\n".join(map(json.dumps, rows)))
    with pytest.raises(RuntimeError, match="friction differs"):
        derive_metrics(path, request)


def test_traction_recipe_is_reproducible():
    assert compile_hazard(scenario()) == compile_hazard(scenario())
    assert compile_hazard(scenario()).friction_coefficient == .05
