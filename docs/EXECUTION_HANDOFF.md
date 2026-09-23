# Execution setup: what is prepared and what remains external

Update September 23, 2026: Token Factory authentication and one real Nemotron inference have passed. This does not provide an AI Cloud GPU worker or a trained G1 policy. See [GPU acceptance and validation](GPU_ACCEPTANCE.md) for the checkpoint downloader, reduced-traction recipe, one-trial GPU acceptance command, and independent metric verifier.

Run `.venv/bin/python -m ghost_trials.execution_setup prepare` once in the project. It creates a private deployment directory containing:

- A cryptographically random worker API token, matched in `worker.env` and `production.env`.
- A dedicated SSH key pair for a GPU VM.
- A production configuration file with actual provider endpoints intentionally empty until those services exist.

The command preserves existing keys and the running dashboard's `.env`. It does not generate Nebius, Hugging Face, or NVIDIA credentials. The directory is ignored by Git, mode 0700, and private files use mode 0600. Never copy this directory to the public static assets.

## Worker endpoint

`bash scripts/start_worker.sh` starts the existing authenticated worker on `127.0.0.1:9000`. This is an actual job API, not a simulated success endpoint:

- `GET /v1/health/ready`: authentication plus runner, GPU, policy server and checkpoint checks. Returns 503 when those prerequisites are absent.
- `POST /v1/jobs`: accepts jobs only after readiness checks pass.
- `GET /v1/jobs/{id}`: returns progress and evidence links.

The host configuration is `deployment/private/worker.env`. Copy it securely to the selected GPU host and update the paths for that host. Run `uv sync --extra worker` in the Ghost Trials checkout before starting the worker there. Keep the worker on a private network or behind an authenticated TLS endpoint.

## Cosmos endpoint

`deployment/cosmos.compose.yaml` runs the official Cosmos Generator NIM on an NVIDIA GPU host. It needs the provider-issued `NGC_API_KEY`, model access, adequate GPU resources, and downloaded model weights. The default bind is localhost:8000. This is independent of the dashboard port 8010. A provider API key cannot be replaced by the locally generated worker token.

The project clients implement `/v1/infer` for Cosmos NIM and `/v1/videos/sync` for vLLM-Omni. They cannot make a model-serving endpoint exist on this CPU-only host. Use the existing GPU bootstrap and installation scripts after a GPU host is available.

## Checkpoint

The public GR00T base model is not a drop-in SONIC policy. NVIDIA's [policy guide](https://github.com/NVIDIA/Isaac-GR00T/blob/main/getting_started/policy.md) identifies `UNITREE_G1_SONIC` as a post-training embodiment. The [SONIC VLA workflow](https://github.com/NVlabs/GR00T-WholeBodyControl/blob/main/docs/source/tutorials/vla_workflow.md) fine-tunes it on collected demonstrations.

For a supplied or trained package:

```bash
.venv/bin/python -m ghost_trials.execution_setup checkpoint /models/g1-sonic/checkpoint-20000
```

The inspector requires the declared embodiment, expected SONIC action names, normalization data and weight shards. It reads safetensors headers and checks data bounds, then hashes relative paths and file contents. Its status is `static_checks_passed`, not a claim of successful GPU inference or task performance. Root and `processor/` metadata layouts are supported. Materialize symlinks before deployment hashing.

The GR00T server launcher now runs this inspection before loading the model. `scripts/train_groot_sonic.sh` already contains NVIDIA's fine-tuning entry point; it requires a processed LeRobot dataset and GPUs. No task dataset or compatible fine-tuned checkpoint is included in this project. A fabricated file or an unrelated checkpoint would not resolve that requirement.

## External account handoff

Nebius [sign-up](https://docs.nebius.com/signup-billing/sign-up) creates a project and requires identity and billing details. The [CLI configuration](https://docs.nebius.com/cli/configure) requires browser sign-in or an authorized service-account key. Neither is available in this session.

The remaining handoff is an authenticated Nebius project with a compute budget, provider/model access, and compatible task data or an existing policy checkpoint. Once available, the prepared code can be deployed and GPU-validated. No VM has been rented and no training run has been performed by this setup command.
