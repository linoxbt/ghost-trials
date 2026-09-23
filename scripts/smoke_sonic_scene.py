"""CPU physics/geometry check only; does not test a trained robot policy.

Usage: uv run --no-project --with mujoco python scripts/smoke_sonic_scene.py
  --source /path/to/scene_43dof.xml --output /tmp/ghost-scene-check
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workers.isaac.sonic_trial import build_scene


def main():
    import mujoco
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = args.output / "smoke-scene.xml"
    build_scene(args.source, scene)
    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    joint = model.joint("ghost_free")
    adr = int(joint.qposadr[0])
    data.qpos[adr:adr + 3] = (2, 0, 1)
    data.qpos[adr + 3:adr + 7] = (1, 0, 0, 0)
    mujoco.mj_forward(model, data)
    start = data.qpos[adr + 2]
    for _ in range(100):
        mujoco.mj_step(model, data)
    assert data.qpos[adr + 2] < start, "The injected box did not fall under gravity"
    assert model.ncam >= 1
    distance = mujoco.mj_geomDistance(model, data, model.geom("ghost_box_geom").id, model.geom("floor").id, 100, None)
    print(f"MuJoCo {mujoco.__version__}: {model.nbody} bodies, {model.njnt} joints, box fell {start - data.qpos[adr + 2]:.3f}m; floor distance {distance:.3f}m")
    print("Geometry/physics smoke passed. GR00T and SONIC decoder execution were not tested.")


if __name__ == "__main__":
    main()
