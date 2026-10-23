# GPU acceptance and independent evidence checks

## Verified so far

The saved Nebius Token Factory key authenticated successfully on September 23, 2026. One real Nemotron Super inference returned a schema-valid insufficient-evidence finding for a deliberately incomplete synthetic fixture (714 total tokens). This validates model access, not robot execution. The local validation report is `data/validation/nebius-connectivity-2026-09-23.json`.

CPU MuJoCo experiments confirm that the new friction intervention changes both automatic and explicit contact-pair friction and increases sliding at lower friction. This is a primitive contact-physics experiment, not a G1 policy evaluation. No GPU VM has been provisioned and no compatible fine-tuned G1 checkpoint has been supplied.

## What the owner needs to supply next

1. A Nebius **AI Cloud** project with GPU quota and authorized access, plus an approved hourly and total compute budget. Token Factory credits/key alone do not establish VM access or a compute allowance. Confirm your actual credit coverage in the console before enabling paid resources. Do not paste private keys into chat.
2. A Hugging Face repository or local directory containing a **fine-tuned `unitree_g1_sonic` policy**, or a processed demonstration dataset and training budget. The public GR00T base and the SONIC controller weights are different pieces; neither alone substitutes for this policy. Save a read-only `HF_TOKEN` privately for gated/private access and accept any required model terms yourself.
3. For Cosmos-generated video, authorized NGC/model access and a deployed Cosmos endpoint. GPU acceptance below deliberately bypasses Cosmos so the robot stack can be tested separately.
4. A robotics reviewer to inspect the actual recording/trace and supply independent labels. No external review has yet occurred.

## Check model access before downloading large weights

Install optional tooling with `uv sync --extra dev --extra physics --extra models`. Then inspect a repository you can access:

```bash
.venv/bin/python -m ghost_trials.checkpoint_access OWNER/FINETUNED_POLICY --revision COMMIT
```

The command resolves an immutable Hub commit, reads only bounded metadata, checks saved SONIC action modalities and normalization availability, and reports the complete selected download size. It never accepts model terms or loads remote Python code. Metadata compatibility is not proof of trained capability.

After reviewing the reported size, opt in to weights download into a **new** directory:

```bash
.venv/bin/python -m ghost_trials.checkpoint_access OWNER/FINETUNED_POLICY \
  --revision COMMIT --download-to /models/g1-sonic --max-download-gb 20
```

20 GB is an example byte ceiling, not a model-size estimate. Use an appropriate reviewed limit. Local structural inspection and content hashing run after the download. Record its checkpoint digest; use the identical directory and digest for the policy server and worker.

## Deploy and accept one trial

Follow [production deployment](PRODUCTION.md) and [execution handoff](EXECUTION_HANDOFF.md). Keep worker GPU/policy checks enabled. With policy checks on, the worker hashes the `GR00T_CHECKPOINT` directory itself (cached until a file changes) and refuses jobs unless it equals `GR00T_CHECKPOINT_DIGEST`, so the checkpoint must be mounted readable in the worker container; jobs must also name the same policy host and port the worker probes. Configure `ISAAC_JOB_ENDPOINT`, `ISAAC_JOB_TOKEN`, `GR00T_CHECKPOINT`, `GR00T_CHECKPOINT_DIGEST` and `GHOST_EXECUTION_BACKEND=gear_sonic_sim` in a private operator environment. Use a TLS endpoint or a localhost SSH tunnel; do not send bearer credentials over public HTTP. The worker's public artifact URL must use the same origin as `ISAAC_JOB_ENDPOINT`.

```bash
# Read-only preflight; never creates a GPU job.
.venv/bin/python -m ghost_trials.gpu_acceptance

# Explicitly execute ONE trial on an already provisioned worker.
.venv/bin/python -m ghost_trials.gpu_acceptance --execute \
  --hazard surface_instability --output data/validation/gpu-traction-001
```

The command pins seed 42 and medium severity, checks worker/backend/checkpoint identity, executes the configured GR00T policy, and downloads a recording, physical recipe, and telemetry. Downloads have byte bounds, reject redirects/cross-origin destinations, and do not forward bearer credentials. Output directories must be new. Errors preserve partial evidence; retries need a new directory. A client timeout does not cancel a queued worker job; inspect the worker before retrying. The worker has its own execution timeout. This command neither provisions nor shuts down a VM, and one trial is not a monetary spending cap.

`--hazard falling_object` and `--hazard path_obstruction` work with either implemented backend. Reduced traction is SONIC/MuJoCo only, not Isaac Arena. Do not label a SONIC/MuJoCo run as an Isaac Sim run. Test and record the Arena backend separately if using it in the submission.

## Separate verification and actual human review

Give the exported bundle and the independently recorded checkpoint digest to a reviewer:

```bash
.venv/bin/python -m ghost_trials.independent_validation \
  data/validation/gpu-traction-001 --expected-checkpoint sha256:YOUR_DIGEST
```

This separate implementation checks artifact hashes, trace ordering, hazard onset, effective friction and metric recomputation. It does not import the worker metric reducer. An MP4 signature check is not full decoding or content inspection. A self-consistent bundle can still be fabricated: these checks are not trusted GPU attestation, an external organization's validation, or safety certification. A proxy response metric remains a proxy after successful verification.

Reviewers must also play the video, compare timestamps and observed behavior, assess measurement quality and model/task validity, and record independent labels. Use the existing `ghost_trials.review_audit` command to compare those labels with findings. Never generate the reference labels using the same judge and call them independent validation.

## Keep the public preview safe

Keep the public deployment on the free CPU providers (`GHOST_MODE=cpu`, with `cpu`/`mujoco_cpu`/`cpu` providers) or the synthetic `local` providers; never point it at the paid GPU providers. Perform paid acceptance privately. Do not expose public generation endpoints using live credentials until execution authorization, rate limits and spending controls are in place.
