"""Run the upstream VLA client and record successful policy calls for provenance."""
import json
import os
from pathlib import Path
import runpy
import time


def main():
    import gr00t.policy.server_client as server_client
    import numpy as np
    original = server_client.PolicyClient

    class RecordedPolicyClient(original):
        def get_action(self, *args, **kwargs):
            action, info = super().get_action(*args, **kwargs)
            motion = action.get("motion_token", action.get("action.motion_token"))
            if motion is None or motion.shape[-1] != 64 or not np.isfinite(motion).all() or np.abs(motion).max() > 1.25:
                raise ValueError("Invalid SONIC motion token from GR00T")
            with Path(os.environ["GHOST_POLICY_CALLS"]).open("a") as stream:
                stream.write(json.dumps({"wall_time": time.time(), "action_shapes": {k: list(np.shape(v)) for k, v in action.items()}}) + "\n")
            return action, info

    server_client.PolicyClient = RecordedPolicyClient
    runpy.run_path("gear_sonic/scripts/run_vla_inference.py", run_name="__main__")


if __name__ == "__main__":
    main()
