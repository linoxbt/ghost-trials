# Live execution, without fabricated robot results

The preview selects Cosmos (`nvidia_catalog`), the remote policy worker
(`isaac_http`), and the real Nebius Nemotron judge. Selection is not proof of
successful execution. Missing credentials/resources block the relevant stage;
live mode never falls back to synthetic measurements.

## Hosted Cosmos video

Sign in at https://build.nvidia.com/nvidia/cosmos3-nano and obtain an API key
through the API panel. Save it privately in `.env`:

```
NVIDIA_API_KEY=<your private key>
COSMOS_API_STYLE=nvidia_catalog
COSMOS_NUM_FRAMES=25
COSMOS_RESOLUTION=480_16_9
```

`COSMOS_BASE_URL` can be empty for hosted generation. The adapter posts the
documented text-to-video request to NVIDIA's Cosmos3 Nano endpoint. It keeps
the original MP4, SHA-256, and generation provenance. A 25-frame video is a
short connection/demo test, not a complete hazard experiment; increase duration
only after measuring latency and trial limits. Hosted trial availability/access
must be confirmed with your account. No GPU rental is required for this endpoint.

Cosmos footage approximates physics; it is not recorded robot-policy execution.
Simulation uses the separately compiled structured hazard recipe, not automatic
reconstruction of a generated video into an identical physical scene.

## Real robot-policy measurements

The remote worker still requires GPU access and compatible fine-tuned weights:

```
ISAAC_JOB_ENDPOINT=https://<your authenticated worker>/
ISAAC_JOB_TOKEN=<private worker token>
GR00T_CHECKPOINT=<compatible fine-tuned checkpoint location>
GR00T_CHECKPOINT_DIGEST=<content digest>
```

Follow [EXECUTION_HANDOFF.md](EXECUTION_HANDOFF.md) and the worker bootstrap
scripts. The generic GR00T base model is not a drop-in UNITREE_G1_SONIC policy.
The SONIC/MuJoCo and Isaac Lab-Arena runners are distinct backends; reduced
traction currently belongs to the SONIC backend, not the Arena implementation.

Missing worker/checkpoint configuration produces a `blocked` trial with no
metrics, score, or judge inference. A finished generated scenario is retained.
After worker setup, replay the blocked trial to execute the saved scenario
without paying for video generation again. A blocked generation stage cannot
be replayed until it has produced a scenario. Interrupted/unknown provider
operations are never automatically retried.

The evidence repository retains worker video/telemetry and checks the artifact
bundle and independently recomputed metrics before judging. If simulation or
evidence capture fails, unverified worker metrics are removed from the trial.
Some implemented measurement methods remain proxies; real execution does not
make them exact geometric distances or causal safety certification.

## Judge verification and spending controls

```
.venv/bin/python -m scripts.check_live_providers
# Up to three bounded inference calls against your Token Factory credits:
.venv/bin/python -m scripts.check_live_providers --judge
```

The judge probe explicitly supplies missing evidence, must return
`insufficient_evidence`, and is never stored as a robot trial or safety score.
Catalog access alone is not an inference test.

Job admission remains disabled until an operator explicitly enables live
execution, configures platform/per-job and organization admission budgets,
and confirms provider-side spending controls. Application reservations are not
provider billing caps. Do not claim that a provider cap exists just to bypass
the gate. Establish the permitted spend with the account owner first.

Restart the backend after changing its private environment. Neither API keys
nor checkpoints belong in Netlify's public frontend bundle.
