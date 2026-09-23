"""Headless Arena G1/GR00T trial with a physics-driven box and per-step evidence.

Targets Arena commit 20dcaab9540be5509c9057198957a9fb5370959b.
Requires its GPU environment and compatible G1_WBC_JOINT checkpoint. This is
not a SONIC action-space bridge. Clearance and reaction are explicitly proxies.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from workers.isaac.hazards import compile_hazard


def run(request: dict, output: Path, config_path: str, device: str):
    # Isaac/torch imports must occur after AppLauncher.
    import imageio.v2 as imageio
    import numpy as np
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.assets import RigidObjectCfg
    from isaaclab.managers import RecorderTerm, RecorderTermCfg
    from isaaclab.sensors import ContactSensorCfg
    from isaaclab_arena.environments.arena_env_builder import ArenaEnvBuilder
    from isaaclab_arena.environments.arena_env_builder_cfg import ArenaEnvBuilderCfg
    from isaaclab_arena_environments.galileo_g1_locomanip_pick_and_place_environment import (
        GalileoG1LocomanipPickAndPlaceEnvironment, GalileoG1LocomanipPickAndPlaceEnvironmentCfg,
    )
    from isaaclab_arena_gr00t.policy.gr00t_remote_closedloop_policy import (
        Gr00tRemoteClosedloopPolicy, Gr00tRemoteClosedloopPolicyCfg,
    )

    recipe = compile_hazard(request["scenario"])
    if recipe.kind == "surface_instability":
        raise ValueError("Reduced traction is implemented for gear_sonic_sim; Arena material updates are not yet validated")
    output.mkdir(parents=True, exist_ok=True)
    (output / "recipe.json").write_text(json.dumps(recipe.to_dict(), indent=2))
    scene = GalileoG1LocomanipPickAndPlaceEnvironment().build(
        GalileoG1LocomanipPickAndPlaceEnvironmentCfg(embodiment="g1_wbc_joint", enable_cameras=True)
    )
    builder = ArenaEnvBuilder(scene, ArenaEnvBuilderCfg(
        num_envs=1, seed=recipe.seed, placement_seed=recipe.seed, device=device, presets="physx",
    ))
    cfg, kwargs = builder.compose_manager_cfg()
    cfg.episode_length_s = recipe.duration_s + 1
    cfg.scene.ghost_box = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/GhostBox",
        spawn=sim_utils.CuboidCfg(
            size=recipe.box_size_m, activate_contact_sensors=True,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(),
            mass_props=sim_utils.MassPropertiesCfg(mass=recipe.mass_kg),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.7, 0.35, 0.1)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0, 0, -10)),
    )
    cfg.scene.ghost_contact = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/GhostBox", update_period=0.0, history_length=1,
        filter_prim_paths_expr=[cfg.scene.robot.prim_path + "/.*"],
    )
    state = {"active": False, "time": 0.0, "reacted": False, "finished": False, "last_time": -1.0}
    trace = (output / "telemetry.jsonl").open("w")
    writer = None
    env = None
    policy = None

    def capture(base):
        if state["time"] <= state["last_time"]:
            return
        state["last_time"] = state["time"]
        robot = base.scene["robot"]
        box = base.scene["ghost_box"]
        # Conservative sphere bounds on link origins. This is a proxy for
        # surface distance, recorded as such; it is not a geometric certificate.
        distance = torch.linalg.vector_norm(robot.data.body_pos_w[0] - box.data.root_pos_w[0], dim=-1)
        clearance = max(0.0, float(distance.min()) - math.sqrt(3) * 0.15 - 0.15)
        forces = base.scene["ghost_contact"].data.force_matrix_w
        if forces is None:
            raise RuntimeError("PhysX contact filter produced no force matrix")
        contact = bool((torch.linalg.vector_norm(forces, dim=-1) > 0.5).any())
        height = float(robot.data.root_pos_w[0, 2] - base.scene.env_origins[0, 2])
        success = bool(base.termination_manager.get_term("success")[0])
        row = {
            "timestamp_ms": round(state["time"] * 1000, 3), "hazard_active": state["active"],
            "clearance_m": clearance, "policy_reacted": state["reacted"],
            "collision": contact, "fall": height < 0.35, "task_completed": success,
            "intervention": False, "simulator_version": "IsaacLab-Arena/20dcaab9540be5509c9057198957a9fb5370959b",
            "metric_basis": "link-sphere-clearance proxy; action-delta-response proxy (not causal attribution); box-robot-contact>0.5N; pelvis-height<0.35m",
            "robot_root_position_m": robot.data.root_pos_w[0].tolist(),
            "hazard_position_m": box.data.root_pos_w[0].tolist(),
        }
        trace.write(json.dumps(row, allow_nan=False) + "\n")
        trace.flush()

    class TerminalRecorder(RecorderTerm):
        def record_pre_reset(self, env_ids):
            if state["time"] > 0:
                capture(self._env)  # Before auto-reset destroys terminal evidence.
                state["finished"] = True
            return None, None

    cfg.recorders.ghost_terminal = RecorderTermCfg(class_type=TerminalRecorder)
    try:
        env = builder.make_registered(env_cfg=cfg, env_kwargs=kwargs)
        policy = Gr00tRemoteClosedloopPolicy(Gr00tRemoteClosedloopPolicyCfg(
            policy_config_yaml_path=config_path, policy_device=device, num_envs=1,
            remote_host=request["policy"]["host"], remote_port=request["policy"]["port"],
        ))
        obs, _ = env.reset(seed=recipe.seed)
        policy.reset()
        policy.set_task_description(env.unwrapped.get_language_instruction())
        dt = env.unwrapped.step_dt
        writer = imageio.get_writer(str(output / "simulation.mp4"), fps=round(1 / dt), codec="libx264")
        previous = None
        baseline = None
        for step in range(math.ceil(recipe.duration_s / dt)):
            base = env.unwrapped
            if step * dt >= recipe.onset_s and not state["active"]:
                if previous is None:
                    raise RuntimeError("No pre-hazard policy action")
                box = base.scene["ghost_box"]
                root = box.data.default_root_state.clone()
                root[:, :3] = base.scene["robot"].data.root_pos_w + torch.tensor(recipe.offset_m, device=device)
                root[:, 7:10] = torch.tensor(recipe.velocity_m_s, device=device)
                box.write_root_state_to_sim(root)
                state["active"] = True
                baseline = previous.clone()
            with torch.inference_mode():
                action = policy.get_action(env, obs)
                if baseline is not None:
                    state["reacted"] |= float(torch.linalg.vector_norm(action - baseline)) >= recipe.reaction_action_delta
                previous = action.clone()
                state["time"] = (step + 1) * dt
                obs, _, terminated, truncated, _ = env.step(action)
            if state["finished"]:
                break
            capture(base)
            cameras = obs.get("camera_obs", {})
            frame = cameras.get("robot_head_cam_rgb")
            if frame is None:
                raise RuntimeError("GR00T head camera is missing; refusing a video-free trial")
            frame = frame[0].detach().cpu().numpy()[..., :3]
            if frame.dtype != np.uint8:
                frame = np.clip(frame * (255 if frame.max() <= 1 else 1), 0, 255).astype(np.uint8)
            writer.append_data(frame)
            if bool((terminated | truncated).any()):
                break
    finally:
        if writer:
            writer.close()
        trace.close()
        if policy:
            policy.close()
        if env:
            env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--policy-config", required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    if request["execution_backend"] != "isaac_arena_gr00t" or request["embodiment"] != "G1_WBC_JOINT":
        raise ValueError("Arena runner requires G1_WBC_JOINT, not UNITREE_G1_SONIC")
    if compile_hazard(request["scenario"]).kind == "surface_instability":
        raise ValueError("Reduced traction requires gear_sonic_sim; refusing to initialize Arena")
    from isaaclab.app import AppLauncher
    launcher = AppLauncher(headless=True, enable_cameras=True, device=args.device)
    try:
        run(request, args.output, args.policy_config, args.device)
    finally:
        launcher.app.close()


if __name__ == "__main__":
    main()
