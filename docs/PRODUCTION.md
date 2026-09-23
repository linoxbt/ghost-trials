# Production integration

This guide separates verified upstream capabilities from Ghost Trials' orchestration layer. Production mode never substitutes synthetic data when a provider fails.

## Compatibility boundary

As of September 13, 2026, there is no documented upstream end-to-end path combining all of these in one process:

- Isaac Lab-Arena
- the `UNITREE_G1_SONIC` modality
- GEAR-SONIC's decoder and whole-body controller

NVIDIA's supported `UNITREE_G1_SONIC` workflow uses the GEAR-SONIC simulation launcher. Isaac Lab-Arena's public G1 closed-loop example instead uses its `g1_wbc_joint` embodiment, a `NEW_EMBODIMENT` modality config, and a separately fine-tuned checkpoint. These are different action spaces and must not be relabeled as each other.

Ghost Trials therefore supports two honest worker backends:

| Backend | Simulator | GR00T configuration | Worker embodiment |
|---|---|---|---|
| `gear_sonic_sim` | GEAR-SONIC simulation | Fine-tuned N1.7, `UNITREE_G1_SONIC`; 78D output | `UNITREE_G1_SONIC` |
| `isaac_arena_gr00t` | Isaac Lab-Arena | Arena's fine-tuned G1 checkpoint and modality config | `G1_WBC_JOINT` |

The worker rejects mismatched backend/embodiment pairs. A future custom SONIC-to-Isaac bridge can be installed behind `ISAAC_ARENA_COMMAND`, but it must emit the required telemetry and be separately validated before its output is accepted.

## Automated deployment order

Account creation, billing authorization, model-license acceptance, and secret issuance are user-owned security operations. After those exist, the repository automates the host setup as follows.

### Cosmos host

```bash
sudo bash scripts/bootstrap_gpu_host.sh cosmos
sudo install -m 600 deployment/gpu-host.env.example /etc/ghost-trials/gpu-host.env
# Fill NGC_API_KEY without committing it.
set -a
source /etc/ghost-trials/gpu-host.env
set +a
echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
docker compose --env-file /etc/ghost-trials/gpu-host.env \
  -f deployment/cosmos.compose.yaml up -d
curl -fsS http://127.0.0.1:8000/v1/health/ready
```

Use an authenticated TLS reverse proxy or a private network between the dashboard and this endpoint. Do not publish an unauthenticated NIM directly to the internet.

### Robotics host

```bash
sudo bash scripts/bootstrap_gpu_host.sh robotics
sudo install -m 600 deployment/gpu-host.env.example /etc/ghost-trials/gpu-host.env
# Fill HF_TOKEN, worker token, URLs, image, and paths.
set -a
source /etc/ghost-trials/gpu-host.env
set +a
sudo -E bash scripts/install_robotics_stack.sh
```

Collect and process a task-specific SONIC dataset before training. The base GR00T model is intentionally rejected for the post-training embodiment tag.

```bash
export ISAAC_GROOT_ROOT=/opt/robotics/Isaac-GR00T
export GR00T_DATASET_PATH=/data/lerobot/g1-ghost-trials
export GR00T_OUTPUT_DIR=/opt/models/g1-sonic
export NUM_GPUS=4
bash scripts/train_groot_sonic.sh

export GR00T_CHECKPOINT=/opt/models/g1-sonic/checkpoint-20000
export GR00T_CHECKPOINT_DIGEST="$(bash scripts/checkpoint_digest.sh "$GR00T_CHECKPOINT")"
bash scripts/start_groot_policy_server.sh
```

The worker only becomes ready when authentication is configured, a GPU is visible, its runner exists, and the GR00T policy port accepts connections. It serializes jobs because Isaac/SONIC own host-level GPU and middleware resources.

```bash
export GHOST_WORKER_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo packaged-source)"
docker compose --env-file /etc/ghost-trials/gpu-host.env \
  -f deployment/worker.compose.yaml up -d --build
curl -H "Authorization: Bearer $ISAAC_WORKER_TOKEN" \
  http://127.0.0.1:9000/v1/health/ready
```

Finally, configure the dashboard's `.env`, run `uv run ghost-trials-preflight`, and only then start production with `make production`.

## 1. Cosmos 3 Generator

The original brief's `/v1/cosmos/.../generate` URL is not a current documented API. Ghost Trials implements both official Cosmos 3 serving contracts:

- Generator NIM: `POST /v1/infer`, JSON response containing `b64_video`
- vLLM-Omni: `POST /v1/videos/sync`, multipart request returning MP4 bytes

For the NIM path, run the official container on a GPU node:

```bash
docker run --runtime=nvidia --gpus all \
  --shm-size=32GB \
  --ulimit nofile=65536:65536 \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/nvidia/cosmos3-generator:1.0.0
```

Check `GET /v1/health/ready`. Configure the dashboard with `COSMOS_API_STYLE=nim` and the service URL. The adapter enforces the documented `4k+1` frame cadence, validates the MP4 container, writes a SHA-256 sidecar, and serves the artifact from `/generated`.

Official reference: <https://github.com/NVIDIA/cosmos#generator-with-nim>

## 2. Structured scenario reasoning

Set `SCENARIO_REASONER_BASE_URL`, `SCENARIO_REASONER_API_KEY`, and `SCENARIO_REASONER_MODEL` to an OpenAI-compatible endpoint. Nebius Token Factory is the default endpoint. The response must be strict JSON matching `StructuredDescription`; invalid model output fails the trial.

## 3. GR00T + GEAR-SONIC

Clone the upstream repositories and download a fine-tuned `UNITREE_G1_SONIC` checkpoint. The base `nvidia/GR00T-N1.7-3B` checkpoint cannot be used directly with this post-training tag.

Start the policy server:

```bash
ISAAC_GROOT_ROOT=/opt/Isaac-GR00T \
GR00T_CHECKPOINT=/models/g1-sonic/checkpoint-final \
GR00T_CHECKPOINT_DIGEST=sha256:YOUR_INSPECTED_CONTENT_DIGEST \
bash scripts/start_groot_policy_server.sh
```

The script starts the official ZMQ server with `--embodiment-tag UNITREE_G1_SONIC`. For interactive simulation, use `scripts/start_gear_sonic_sim.sh`. A non-interactive trial command configured as `GEAR_SONIC_SIM_COMMAND` must inject the request's scenario and produce:

- `simulation.mp4`
- `telemetry.jsonl`, following `workers/isaac/telemetry.schema.json`

The worker derives all certification metrics from that trace. Missing hazard activation, clearance samples, video, or trace causes failure rather than fabricated metrics.

Official references:

- <https://github.com/NVIDIA/Isaac-GR00T>
- <https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vla_inference.html>

## 4. Isaac Lab-Arena alternative

Install Isaac Lab-Arena with its GR00T dependencies and accept the Isaac Sim EULA. Its official evaluation entry point is `isaaclab_arena/evaluation/policy_runner.py`; there is no `lab-arena run` executable.

The current upstream G1 command uses:

```bash
python isaaclab_arena/evaluation/policy_runner.py \
  --policy_type isaaclab_arena_gr00t.policy.gr00t_remote_closedloop_policy.Gr00tRemoteClosedloopPolicy \
  --policy_config_yaml_path isaaclab_arena_gr00t/policy/config/g1_locomanip_gr00t_closedloop_config.yaml \
  --remote_host 127.0.0.1 \
  --remote_port 5555 \
  --num_episodes 1 \
  --enable_cameras \
  --record_camera_video \
  --output_base_dir /data/ghost-trials/run \
  galileo_g1_locomanip_pick_and_place \
  --object brown_box \
  --embodiment g1_wbc_joint
```

For Ghost Trials hazards, register an Arena environment that activates the requested hazard at the supplied seed and records the telemetry schema. Point `ISAAC_ARENA_COMMAND` at that environment's non-interactive wrapper. Stock task success alone is insufficient for reaction-time or clearance certification, so the worker will reject it without telemetry.

Official reference: <https://github.com/isaac-sim/IsaacLab-Arena/blob/main/docs/pages/example_workflows/locomanipulation/step_5_evaluation.rst>

## 5. GPU worker

Build `workers/isaac/Dockerfile` on top of the exact Isaac Lab-Arena image used by your benchmark:

```bash
docker build \
  -f workers/isaac/Dockerfile \
  --build-arg ARENA_IMAGE=your-pinned-arena-image \
  -t ghost-trials-worker .
```

Run it with the NVIDIA runtime, the policy/model volumes, and the environment values in `deployment/production.env.example`. Expose port 9000 only through authenticated TLS. The API is:

- `GET /v1/health/ready`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /artifacts/{job_id}/{filename}`

## 6. Dashboard production mode

Fill `deployment/production.env.example`, then run:

```bash
set -a
source deployment/production.env
set +a
uv run ghost-trials-preflight
uv run uvicorn ghost_trials.app:app --host 0.0.0.0 --port 8000
```

Preflight must pass before recording the demo. Pin and record the Cosmos container digest, Arena/Isaac commit, GR00T commit, GEAR-SONIC commit, policy checkpoint digest, scenario seed, and generated artifact hashes for the final evidence chain.
