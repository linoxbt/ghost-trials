"""Observe a G1's DDS state/commands and record a local camera. NO actuation.

Requires an on-site operator, SDK2 installation, and an externally running
compatible policy. This module does not deploy a controller, clear robot modes,
publish commands, generate hazards, or implement an emergency stop.
"""
import argparse
import json
import math
import re
import subprocess
import threading
import time
from pathlib import Path

from ghost_trials.physical import CaptureMetadata, RecordingSetup, VERSION, file_digest


class G1Observer:
    def __init__(self, interface):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,32}", interface) or interface == "lo":
            raise ValueError("Select the physical robot's network interface, not loopback")
        # Import subscribers only. Never import a publisher or motion client.
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_, LowCmd_
        self.lock = threading.Lock()
        self.state, self.command = None, None
        ChannelFactoryInitialize(0, interface)
        self.subscribers = [ChannelSubscriber("rt/lowstate", LowState_), ChannelSubscriber("rt/lowcmd", LowCmd_)]
        self.subscribers[0].Init(self.on_state, 10)
        self.subscribers[1].Init(self.on_command, 10)

    def on_state(self, message):
        values = [float(m.q) for m in message.motor_state[:29]]
        imu = [float(v) for v in message.imu_state.rpy]
        if len(values) != 29 or len(imu) != 3 or not all(math.isfinite(v) for v in values + imu):
            return
        with self.lock:
            self.state = (time.monotonic(), values, imu)

    def on_command(self, message):
        values = [float(m.q) for m in message.motor_cmd[:29]]
        if len(values) != 29 or not all(math.isfinite(v) for v in values):
            return
        with self.lock:
            self.command = (time.monotonic(), values)

    def sample(self):
        with self.lock:
            state, command = self.state, self.command
        now = time.monotonic()
        if not state or (now-state[0])*1000 > 200:
            raise RuntimeError("Robot state missing or stale; recording stops without commanding the robot")
        fresh_command = command if command and (now-command[0])*1000 <= 200 else None
        return {"state_age_ms": (now-state[0])*1000, "joint_positions_rad": state[1],
            "imu_rpy_rad": state[2], "policy_command_rad": fresh_command[1] if fresh_command else None,
            "command_age_ms": (now-fresh_command[0])*1000 if fresh_command else None}

    def close(self):
        for subscriber in self.subscribers:
            subscriber.Close()


def capture(args):
    setup_data = json.loads(args.setup.read_text())
    setup = RecordingSetup.model_validate(setup_data.get("setup", setup_data))
    if not args.confirm_on_site or not setup.on_site_operator_confirmed or setup.robot_variant != "g1_29dof":
        raise ValueError("On-site confirmation and a locally checked 29-DOF G1 are required")
    if not re.fullmatch(r"/dev/video\d+", args.camera_device):
        raise ValueError("Use a local V4L2 camera device")
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    observer = G1Observer(args.interface)
    process = None
    marker_lock = threading.Lock()
    flags = {"hazard_active": False, "task_completed": False, "collision_observed": False,
             "fall_observed": False, "intervention_active": False}
    stopped = threading.Event()
    def marker_input():
        print("Observe only. Mark events AFTER observation: onset, complete, collision, fall, intervention, resumed, stop.")
        while not stopped.is_set():
            try:
                marker = input().strip().lower()
            except EOFError:
                stopped.set()
                return
            with marker_lock:
                if marker == "onset": flags["hazard_active"] = True
                elif marker == "complete": flags["task_completed"] = True
                elif marker == "collision": flags["collision_observed"] = True
                elif marker == "fall": flags["fall_observed"] = True
                elif marker == "intervention": flags["intervention_active"] = True
                elif marker == "resumed": flags["intervention_active"] = False
                elif marker == "stop": stopped.set()
    try:
        deadline = time.monotonic()+10
        while observer.state is None or observer.command is None:
            if time.monotonic() > deadline:
                raise RuntimeError("No fresh state/policy command stream; check DDS connectivity and the on-site policy")
            time.sleep(.05)
        observer.sample()
        # Camera launch is an estimated alignment, not an asserted hardware trigger.
        started = time.monotonic()
        process = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "v4l2", "-framerate", "20", "-video_size", "640x480", "-i", args.camera_device,
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-t", str(args.duration), "-fs", "200000000", str(args.output / "response.mp4")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=marker_input, daemon=True).start()
        with (args.output / "telemetry.jsonl").open("x") as output:
            while not stopped.is_set() and time.monotonic()-started < args.duration:
                if process.poll() is not None:
                    raise RuntimeError("Camera recording ended unexpectedly; no completed bundle is produced")
                now = time.monotonic()
                sample = observer.sample()
                with marker_lock:
                    sample.update(flags)
                sample.update(timestamp_ms=(now-started)*1000, clearance_m=None)
                output.write(json.dumps(sample, allow_nan=False)+"\n")
                output.flush()
                time.sleep(.02)
        stopped.set()
        # SIGINT lets ffmpeg finish the MP4 trailer; it does not touch the robot.
        import signal
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
        if process.returncode not in {0, 255}:
            raise RuntimeError("Camera capture failed")
        metadata = CaptureMetadata(schema_version=VERSION, robot_serial=setup.robot_serial,
            robot_variant="g1_29dof", checkpoint_digest=setup.checkpoint_digest,
            controller_name=setup.policy_name, observer_only=True,
            operator_confirmed_physical_hardware=True, clock_basis="capture_host_monotonic",
            video_offset_ms=0.0, video_sync_uncertainty_ms=500.0, command_change_threshold_rad=.03)
        (args.output / "capture.json").write_text(metadata.model_dump_json(indent=2))
        from ghost_trials.physical import FILES, verify_recording
        manifest = {name: {"bytes": (args.output/name).stat().st_size,
                    "sha256": file_digest(args.output/name)} for name in FILES}
        verify_recording(args.output, setup, manifest)
        print("Recording bundle verified locally. Hardware/policy identity and camera alignment still need on-site review.")
    finally:
        stopped.set()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        observer.close()


def main():
    def seconds(value):
        number = int(value)
        if not 5 <= number <= 300:
            raise argparse.ArgumentTypeError("Duration must be between 5 and 300 seconds")
        return number
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing data is never overwritten")
    parser.add_argument("--interface", required=True)
    parser.add_argument("--camera-device", default="/dev/video0")
    parser.add_argument("--duration", type=seconds, default=60, metavar="5..300")
    parser.add_argument("--confirm-on-site", action="store_true")
    capture(parser.parse_args())


if __name__ == "__main__":
    main()
