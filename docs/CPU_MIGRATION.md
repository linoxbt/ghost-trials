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

### Public CPU backend

The Netlify site (`https://ghosttrials.site`) is a static frontend whose
`_redirects` proxy API routes to a single CPU container on a self-hosted VPS at
`https://backend.ghosttrials.site`. On 22 October 2026 the backend moved there
from Railway after Railway suspended services; the database started fresh.
Verify `/health` and a signed-in Hunt after each release.

The VPS layout (`/opt/ghost-trials`):

- `compose.yaml` runs the image built from this repository
  (`docker build -t ghost-trials-api:<sha> .`), published only on
  `127.0.0.1:8796`, with `./data:/data`, `cap_drop: ALL` plus the
  `CHOWN`, `DAC_READ_SEARCH`, `SETUID` and `SETGID` capabilities the entrypoint
  needs to hand `/data` to UID 10001, and a memory limit.
- `ghost-trials.env` (mode `600`, never committed) holds the variables below.
- `data/` holds the SQLite state and evidence artifacts, owned by UID 10001.
- Caddy terminates TLS with a `backend.ghosttrials.site { reverse_proxy 127.0.0.1:8796 }`
  site block.

```dotenv
GHOST_MODE=cpu
GHOST_SCENARIO_PROVIDER=cpu
GHOST_SIMULATOR_PROVIDER=mujoco_cpu
GHOST_JUDGE_PROVIDER=cpu
GHOST_EXECUTION_BACKEND=mujoco_cpu
GHOST_PUBLIC_DEPLOYMENT=true
GHOST_CUSTOMER_AUTH_REQUIRED=true
GHOST_AUTH_PROVIDER=privy
PRIVY_APP_ID=<your Privy public app ID>
GHOST_COOKIE_SECURE=true
GHOST_ALLOWED_ORIGINS=https://ghosttrials.site,https://ghost-trials.netlify.app,https://backend.ghosttrials.site
GHOST_DATA_PATH=/data/state.sqlite3
GHOST_ARTIFACT_ROOT=/data/artifacts
GHOST_TRUSTED_PROXY_HOPS=0
```

Enable the desired sign-in methods in the connected Privy app and allow the
Netlify origin. Dynamic remains an alternative identity adapter, not the
currently used path. Do not set a provider ID for an app you do not own.
The backend refuses to start with `GHOST_PUBLIC_DEPLOYMENT=true` if individual
sign-in, secure cookies, or exact HTTPS origins are missing. The container
entrypoint assigns its dedicated `/data` mount, then runs FastAPI as UID 10001.
Keep exactly one replica because the state store uses SQLite and an exclusive
process lease. Back up `data/` off-host as well as on it.

`GHOST_TRUSTED_PROXY_HOPS` is `0` here because Caddy replaces
`X-Forwarded-For` with the Netlify edge address, so no client address is
trustworthy. That is safe for sign-in: credentials are verified first and only
failures are counted, so a flood of junk tokens can return 429 to itself but
never blocks a valid sign-in. Set the value to the number of proxies that append
`X-Forwarded-For` only after checking a request log. Trial admission is capped
per workspace (`GHOST_MAX_ORG_PENDING_JOBS`, `GHOST_MAX_ORG_JOBS_PER_DAY`) and per
signed-in person across all of their workspaces (`GHOST_MAX_SUBJECT_PENDING_JOBS`,
`GHOST_MAX_SUBJECT_JOBS_PER_DAY`), under the platform caps.

Pages from both the backend and Netlify carry an enforced Content Security
Policy (`ghost_trials/csp.py`, Privy's published origins); browsers report
violations to `/csp-report`, which logs only the directive and blocked host.
Physical recording uploads are bounded per workspace and platform-wide
(`GHOST_PHYSICAL_*_STORAGE_BYTES`); cancelled or abandoned sessions are deleted, and a validated
recording's files can be deleted from the Physical page to free its quota.

Review budgets: `python -m ghost_trials.budget list` and
`python -m ghost_trials.budget set <organization_id> <cents>`, run inside the
container as UID 10001. A nightly cron job (`/opt/ghost-trials/backup.sh`) keeps
seven days of consistent online database snapshots and artifact archives on the
host; copy them off-host for real disaster recovery.

To release a new backend build, build a new image tag, update it in
`compose.yaml`, and run `docker compose up -d`. If you deploy on Railway
instead, the API still refuses to start unless `GHOST_DATA_PATH` and
`GHOST_ARTIFACT_ROOT` are under the attached volume's
`RAILWAY_VOLUME_MOUNT_PATH`.

Keep the Netlify production build variable `GHOST_BACKEND_ORIGIN` set to
`https://backend.ghosttrials.site` and redeploy the frontend when static assets
change. Check that Netlify `/health` returns 200, unauthenticated `/trials`
returns 401, and an authenticated user can start and inspect a CPU Hunt. A Git
push alone does not invoke the repository's manual frontend deployment workflow.

The active CPU settings are `GHOST_MODE=cpu`, `GHOST_SCENARIO_PROVIDER=cpu`, `GHOST_SIMULATOR_PROVIDER=mujoco_cpu`, `GHOST_JUDGE_PROVIDER=cpu`, `GHOST_EXECUTION_BACKEND=mujoco_cpu`, and `GHOST_POLICY_NAME=gantry-push-v1`. The container entrypoint now defaults to public-deployment safeguards and refuses startup without individual sign-in and exact HTTPS origins. For loopback-only Docker development, explicitly set `GHOST_PUBLIC_DEPLOYMENT=false` and do not publish the port beyond localhost. If an existing `.env` selects production/GPU providers, set the CPU values explicitly in the deployment environment; never publish keys in frontend variables. Persistent data and artifacts should be mounted or backed up. A development server on port 8000 must not be exposed directly.

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

The existing Cosmos video, GPU Nemotron judge, SONIC/Isaac worker, hardware capture, and Privy/Dynamic authentication paths remain available. CPU physics never requires them. An optional **separate** Nebius/Nemotron CPU reviewer calls one Super model per verified trial only when its explicit enable switch, credentials, budgets, and operator-confirmed provider spending controls are present. The review cannot change the deterministic task outcome and does not cause a synthetic fallback. The old G1 policy action spaces are not interchangeable with this gantry controller. CPU mode does not create Cosmos video. It is a physically simulated manipulation benchmark, not a hardware trial, a G1 benchmark, or a safety certification. Neural checkpoints outside the declared JSON observation/action contract remain unsupported.
