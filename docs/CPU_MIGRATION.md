# CPU MuJoCo execution

Ghost Trials defaults to a headless, CPU-only MuJoCo task. This is a migration of the existing `ScenarioGenerator → Simulator → TrialJudge → evidence → Hunt` pipeline, not a replacement of the GPU adapters. The CPU backend is independent of CUDA, Isaac, Cosmos, Nebius, and local NVIDIA inference. It does not evaluate a Unitree G1, GR00T, or SONIC checkpoint. Select the GPU path explicitly if those are the policy under test.

## Executable task

The `ghost-gantry-xy-v1` model is a two-prismatic-joint gantry arm with a spherical pusher, free tabletop block, position actuators, limited joint ranges and force, gravity, friction, and contact. The task is to place the block center in x = 0.64–0.86 m and |y| ≤ 0.12 m by 3.0 simulated seconds. `gantry-push-v1` and `gantry-push-v2` are actual, versioned deterministic controllers with content digests. `gantry-mlp-example` is a lightweight feed-forward neural policy executed entirely on CPU; it is an example checkpoint, not a trained production policy. Selecting any registered policy executes that exact policy; an unsupported identifier is rejected, never substituted. None are GR00T or SONIC weights.

An operator can register a compatible neural checkpoint by placing a validated `ghost-cpu-mlp-v1` JSON file named `<policy-id>.json` in `ghost_trials/policies/cpu/` or in the directory selected by `GHOST_CPU_POLICY_DIR`. The fixed observation contract is `[elapsed_control_time/3, block_x_m, pusher_x_m, block_vx_m_s]`; hidden layers use `tanh`, the scalar output uses a sigmoid mapped to a 0.1–0.9 m x-axis actuator target. Policies have one to three layers, at most 16 units per layer, finite bounded weights, a declared version and robot-model identity, and a SHA-256 content digest. No arbitrary Python checkpoint code is loaded. This format does **not** accept GR00T/SONIC/PyTorch weights directly; conversion and observation/action validation are required before evaluation.

The Hunt can change only parameters wired into the model or controller:

| Parameter | Range | Mechanism |
|---|---:|---|
| `object_mass_kg` | 0.05–1.0 kg | Block geom mass |
| `surface_friction` | 0.1–1.2 | Table and block contact friction |
| `object_position_x_m` | 0.35–0.50 m | Initial free-block pose |
| `controller_delay_s` | 0–1.2 s | Delay before commanded arm motion |

Recipes contain the complete values, schema version, and seed; the seed deterministically perturbs the initial block y pose by at most 3 mm. Unsupported keys or out-of-range values are rejected before execution. Search is bounded; a failure boundary is empirical within the tested policy, task, simulator version, and parameter region, not a universal safety threshold. MuJoCo's deterministic stepping and pinned recipe support exact replay on a comparable platform; floating-point differences across platforms may change outcomes near a threshold.

## Local / CPU VPS setup

Start with **2 vCPU and 4 GiB RAM** as a practical provisioning target, not a measured minimum or performance guarantee. The worker has a 20-second wall-clock timeout, an 18-second CPU-time soft limit, and a 2.5 GB virtual-address-space cap. Run one Hunt at a time on a small host and benchmark before raising `GHOST_MAX_PENDING_JOBS` or daily budgets. Each physics trial simulates 3.0 seconds in 600 steps without rendering. The physics subprocess keeps FastAPI requests responsive and is killed on timeout/cancellation; an incomplete trial is an error, not a robot failure.

```bash
cp .env.example .env  # only on a fresh local checkout; do not overwrite an existing private .env
npm ci
npm run build:auth
uv sync --frozen --extra dev
uv run uvicorn ghost_trials.app:app --host 127.0.0.1 --port 8000
```

For an existing checkout whose private `.env` still selects GPU providers, use `uv run python -m scripts.run_cpu` to override only the execution-mode variables without changing or printing secrets.

The active CPU settings are `GHOST_MODE=cpu`, `GHOST_SCENARIO_PROVIDER=cpu`, `GHOST_SIMULATOR_PROVIDER=mujoco_cpu`, `GHOST_JUDGE_PROVIDER=cpu`, `GHOST_EXECUTION_BACKEND=mujoco_cpu`, and `GHOST_POLICY_NAME=gantry-push-v1`. For a CPU-only Docker host, `docker compose up --build` uses these defaults if `.env` is absent. If an existing `.env` selects production/GPU providers, set the CPU values explicitly in the deployment environment; never publish keys in frontend variables. Persistent data and artifacts should be mounted or backed up. Protect public deployments with the existing authentication and HTTPS reverse proxy; a development server on port 8000 must not be exposed directly.

## Evidence and measurements

Each completed trial retains `recipe.json`, `summary.json`, `telemetry.jsonl`, `trajectory.svg`, and a SHA-256 manifest. The SVG is drawn from recorded MuJoCo state; it is **not video**. The independent bundle checker validates file hashes, monotonic timestamps, controller digest, model recipe, sample count, starting and final block state, displacement, task outcome, and simulated duration. Hashes verify integrity of retained files, not trusted hardware execution or an external expert's attestation. No robot-camera recording is claimed.

Telemetry samples every five physics steps: simulated time, arm joint positions/velocities, pusher and block positions, block velocity, controller target, sampled pusher–block contact force, controller tracking error, block tilt, and limit-violation flag. The summary includes simulated duration and separately measured wall-clock/controller time, first contact, maximum contact force and tracking error over **all** steps, sampled pusher–block contact count, pusher–table contact-onset event count, task completion, and controller/model provenance. `pusher_object_contact_count` is a count of sampled contact flags, not a physical time duration. The versioned CPU rubric maps the measured task outcome into the legacy category field; a category is not a calibrated safety score.

Run the full API/queue/worker/Hunt/replay/regression smoke with retained artifacts:

```bash
uv run python -m scripts.cpu_smoke --strategy grid --trials 9 --output data/cpu-validation
uv run pytest -q
```

`scripts.cpu_smoke` exits nonzero if no verified failure, replay, or regression completes. The automated CPU test actually executes MuJoCo, including a lightweight neural policy, and checks that modifying telemetry breaks verification. Synthetic algorithm fixtures remain separate and are not physics evidence.

## Optional integrations and limits

The existing Cosmos video, Nemotron judge, SONIC/Isaac worker, hardware capture, Privy authentication, and deployment paths remain available. They are not invoked by the CPU path. The old G1 policy action spaces are not interchangeable with this gantry controller. CPU mode does not create Cosmos video or Nemotron commentary. It is a physically simulated manipulation benchmark, not a hardware trial, a G1 benchmark, or a safety certification. Neural checkpoints outside the declared JSON observation/action contract remain unsupported.
