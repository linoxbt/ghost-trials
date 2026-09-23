"""Simulation-only SONIC process supervisor. Run using SONIC's .venv_sim Python.

The C++ decoder and VLA client run in their upstream environments. This harness
never selects a hardware interface: deploy.sh receives the literal 'sim'.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from workers.isaac.hazards import compile_hazard
from workers.isaac.traction import GroundTraction


def build_scene(source: Path, target: Path):
    """Flatten local includes and preserve their asset paths in the job directory."""
    def expand(path):
        root = ET.parse(path).getroot()
        for compiler in root.findall("compiler"):
            for key in ("meshdir", "texturedir"):
                if compiler.get(key):
                    compiler.set(key, str((path.parent / compiler.get(key)).resolve()))
        for parent in list(root.iter()):
            for item in list(parent):
                if item.tag == "include":
                    nested = expand((path.parent / item.attrib["file"]).resolve())
                    index = list(parent).index(item)
                    parent.remove(item)
                    for child in reversed(list(nested)):
                        parent.insert(index, child)
        return root

    root = expand(source.resolve())
    world = ET.SubElement(root, "worldbody")
    box = ET.SubElement(world, "body", name="ghost_box", pos="0 0 -10")
    ET.SubElement(box, "freejoint", name="ghost_free")
    ET.SubElement(box, "geom", name="ghost_box_geom", type="box", size="0.15 0.15 0.15", mass="2", rgba="0.7 0.35 0.1 1")
    ET.SubElement(world, "camera", name="ghost_witness", pos="3 -3 2.5", xyaxes="0.707 0.707 0 -0.3 0.3 0.9")
    ET.ElementTree(root).write(target, encoding="unicode")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sonic-root", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    if request["execution_backend"] != "gear_sonic_sim" or request["embodiment"] != "UNITREE_G1_SONIC":
        raise ValueError("SONIC runner requires UNITREE_G1_SONIC")
    recipe = compile_hazard(request["scenario"])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = args.sonic_root.resolve()
    inference_python = root / ".venv_inference/bin/python"
    if not inference_python.is_file():
        raise RuntimeError("Install the upstream SONIC inference environment first")
    os.environ.setdefault("MUJOCO_GL", "egl")
    os.chdir(root)
    sys.path.insert(0, str(root))

    import imageio.v2 as imageio
    import mujoco
    import numpy as np
    import zmq
    from gear_sonic.utils.mujoco_sim import base_sim
    from gear_sonic.utils.mujoco_sim.configs import SimLoopConfig
    from gear_sonic.utils.mujoco_sim.sim_utils import get_subtree_body_ids

    config = SimLoopConfig(enable_onscreen=False, enable_offscreen=True, enable_image_publish=True).load_wbc_yaml()
    config["INTERFACE"] = "lo"
    scene = output / "sonic_scene.xml"
    build_scene(root / config["ROBOT_SCENE"], scene)
    config["ROBOT_SCENE"] = str(scene)
    (output / "recipe.json").write_text(json.dumps({**recipe.to_dict(), "task": "walk forward 1m", "simulator": "MuJoCo/GEAR-SONIC"}, indent=2))

    # Upstream auto-resets on a fall. Preserve terminal state for the recorder.
    class TrialEnv(base_sim.DefaultEnv):
        def check_fall(self):
            self.fall = bool(self.mj_data.qpos[2] < 0.2)

    base_sim.DefaultEnv = TrialEnv
    simulator = base_sim.BaseSimulator(config, onscreen=False, offscreen=True, enable_image_publish=True)
    env = simulator.sim_env
    model, data = env.mj_model, env.mj_data
    box_joint = model.joint("ghost_free")
    qadr, vadr = int(box_joint.qposadr[0]), int(box_joint.dofadr[0])
    box_geom = model.geom("ghost_box_geom").id
    bodies = set(get_subtree_body_ids(model, env.root_body_id))
    robot_geoms = [i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in bodies and (model.geom_contype[i] or model.geom_conaffinity[i])]
    if not robot_geoms:
        raise RuntimeError("G1 collision geometry is missing")
    traction = GroundTraction(model, recipe.friction_coefficient) if recipe.kind == "surface_instability" else None
    renderer = mujoco.Renderer(model, height=480, width=640)
    context = zmq.Context()
    keyboard = context.socket(zmq.PUB)
    keyboard.bind("tcp://127.0.0.1:5580")
    processes = []
    logs = []
    marker = output / "policy_calls.jsonl"
    writer = None
    trace = None

    def launch(command, name, stdin=None):
        log = (output / f"{name}.log").open("wb")
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=stdin,
                                   env={**os.environ, "PYTHONUNBUFFERED": "1", "GHOST_POLICY_CALLS": str(marker)})
        processes.append(process)
        return process

    try:
        simulator.start_image_publish_subprocess(camera_port=5555)
        deploy = launch([
            "bash", str(root / "gear_sonic_deploy/deploy.sh"),
            "--cp", "policy/sonic_v1_1/model", "--obs-config", "policy/sonic_v1_1/observation_config.yaml",
            "--input-type", "zmq_manager", "--motor-kp-scale", "4,10=1.5", "--motor-kd-scale", "4,10=1.5", "sim",
        ], "decoder", stdin=subprocess.PIPE)
        deploy.stdin.write(b"\n")
        deploy.stdin.close()
        launch([
            str(inference_python), str(Path(__file__).with_name("sonic_vla.py")),
            "--host", request["policy"]["host"], "--port", str(request["policy"]["port"]),
            "--embodiment-tag", "unitree_g1_sonic", "--prompt", "walk forward one meter and avoid obstacles",
            "--camera-host", "127.0.0.1", "--camera-port", "5555",
        ], "vla")
        started = time.monotonic()
        command_stage = 0
        command_time = started
        episode_start = None
        initial_position = None
        active = False
        reacted = False
        baseline = None
        writer = imageio.get_writer(str(output / "simulation.mp4"), fps=25, codec="libx264")
        trace = (output / "telemetry.jsonl").open("w")
        tick = 0
        while True:
            wall_start = time.monotonic()
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("Decoder or VLA process exited; inspect decoder.log and vla.log")
            if wall_start - started > 300 and episode_start is None:
                raise TimeoutError("SONIC initialization produced no confirmed GR00T inference in 300s")
            if episode_start is None:
                ready_log = output / "vla.log"
                ready = "Starting the policy loop" in ready_log.read_text(errors="replace")
                if ready and wall_start - command_time > 2 and command_stage < 3:
                    keyboard.send_string(("k", "i", "p")[command_stage])
                    command_stage += 1
                    command_time = wall_start
                if marker.is_file() and marker.stat().st_size and command_stage == 3:
                    episode_start = float(data.time)
                    initial_position = data.qpos[:3].copy()
                    if env.elastic_band:
                        env.elastic_band.enable = False
            elapsed = float(data.time) - episode_start if episode_start is not None else 0
            if elapsed >= recipe.onset_s and not active:
                if traction:
                    traction.activate()
                else:
                    data.qpos[qadr:qadr + 3] = data.qpos[:3] + np.array(recipe.offset_m)
                    data.qpos[qadr + 3:qadr + 7] = [1, 0, 0, 0]
                    data.qvel[vadr:vadr + 3] = recipe.velocity_m_s
                    data.qvel[vadr + 3:vadr + 6] = 0
                baseline = env.compute_body_qpos().copy()
                active = True
                mujoco.mj_forward(model, data)
            if not active or traction:
                data.qpos[qadr:qadr + 3] = [0, 0, -10]
                data.qvel[vadr:vadr + 6] = 0
            env.sim_step()
            if tick % max(1, round(0.04 / env.sim_dt)) == 0:
                env.update_render_caches()
                if episode_start is not None:
                    renderer.update_scene(data, camera="ghost_witness")
                    writer.append_data(renderer.render())
            if episode_start is not None:
                if time.time() - marker.stat().st_mtime > 30:
                    raise TimeoutError("GR00T policy has not returned a valid action in 30s")
                # Geometric distance uses MuJoCo collision geoms, not the generated video.
                clearance = None if traction else min(mujoco.mj_geomDistance(model, data, box_geom, geom, 100, None) for geom in robot_geoms)
                traction_observation = traction.observe(data, robot_geoms) if traction else {}
                if traction:
                    collision = any((int(c.geom1) in robot_geoms and int(c.geom2) not in robot_geoms and int(c.geom2) not in traction.ground) or
                                    (int(c.geom2) in robot_geoms and int(c.geom1) not in robot_geoms and int(c.geom1) not in traction.ground) for c in data.contact)
                else:
                    collision = any((int(c.geom1) == box_geom and int(c.geom2) in robot_geoms) or
                                    (int(c.geom2) == box_geom and int(c.geom1) in robot_geoms) for c in data.contact)
                if baseline is not None:
                    reacted |= float(np.linalg.norm(env.compute_body_qpos() - baseline)) >= recipe.reaction_action_delta
                completed = bool(data.qpos[0] - initial_position[0] >= 1.0 and not env.fall)
                trace.write(json.dumps({
                    "timestamp_ms": (float(data.time) - episode_start) * 1000,
                    "hazard_active": active, "policy_reacted": reacted,
                    "clearance_m": max(0.0, float(clearance)) if clearance is not None else None, "collision": collision, "fall": env.fall,
                    **traction_observation,
                    "task_completed": completed, "intervention": False,
                    "simulator_version": f"MuJoCo/{mujoco.__version__};SONIC/087f9ac01d46f6d8e4d0b73c01ae64799f292a38",
                    "metric_basis": ("MuJoCo whole-plane sliding friction step; contact-point tangential speed; motor-target-delta response proxy; root-height fall proxy; goal forward 1m"
                                     if traction else "MuJoCo collision-geom distance; motor-target-delta response proxy, not causal attribution; goal forward 1m"),
                }, allow_nan=False) + "\n")
                if elapsed >= recipe.duration_s or env.fall:
                    break
            tick += 1
            time.sleep(max(0, env.sim_dt - (time.monotonic() - wall_start)))
    finally:
        if traction:
            traction.restore()
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if writer:
            writer.close()
        if trace:
            trace.close()
        for log in logs:
            log.close()
        keyboard.close(linger=0)
        context.term()
        renderer.close()
        simulator.close()


if __name__ == "__main__":
    main()
