# Ghost Trials

Ghost Trials is an auditable simulation safety-evaluation workspace for robotics engineers. It organizes hazard scenarios, robot-policy trials, measured evidence, and model-assisted findings. Its results describe the tested conditions, not real-world safety certification.

This repository is the runnable product shell for the Nebius × NVIDIA Global AI Hackathon Physical AI track. It runs without GPU credentials using deterministic development adapters. Those adapters preserve the production contracts, so Cosmos generation and Isaac Lab-Arena jobs can replace them without changing the API or dashboard.

## Quick start

Requirements: Python 3.11+ and `uv`.

```bash
cp .env.example .env
uv sync --extra dev
uv run uvicorn ghost_trials.app:app --reload
```

Open <http://127.0.0.1:8000> for the animated landing page, `/docs` for documentation, or `/app/` for the evaluation workspace. The first development start seeds six synthetic trials. Submit a demo hazard to create a scenario, schematic preview, synthetic metrics, and a rubric finding. This does not generate Cosmos video or execute a GPU policy.

For a phone on the same network, run `make mobile`, determine this machine's LAN IP, and open `http://<LAN-IP>:8000` on the phone. Do not expose the development server directly to the public internet.

```bash
uv run pytest
```

Or use Docker:

```bash
docker compose up --build
```

## Current build

- FastAPI API: `POST /scenarios`, `GET /trials`, `GET /trials/{id}`, `GET /safety-score`, and `WS /live`
- Persistent, typed scenario and evaluation records
- Seeded, replayable simulation metric adapter
- Fixed safety rubric with evidence-citing causal reports
- Optional Nebius Token Factory / Nemotron judge with two-pass disagreement detection and Ultra escalation
- Orange application interface with custom vector branding, collapsible sidebar, and accessible mobile hamburger navigation
- Separate Overview, Trial Runs, Scenario Library, Create Trial, Reports, System, and flight-record views
- Searchable/filterable trial records, live progress, and JSON evidence exports
- Compare runs with setup compatibility checks, metric deltas, and linked recording controls
- Evidence inspector with recorded incident timestamps, provenance, artifact manifests, and original judge interpretations
- Benchmark coverage split by policy/checkpoint, simulator, rubric, embodiment, and evidence origin
- Versioned score guardrails: insufficient evidence is excluded; collisions are not causal proof; incompatible cohorts are not pooled
- Exact saved-scenario replay against the configured policy, without regenerating the hazard
- Opt-in bounded adaptive/random/grid experiment CLI and reference-label agreement audit

See [the frontend guide](docs/FRONTEND.md) for view URLs, brand assets, and browser checks.

The default `local` mode is intentionally a development adapter. Its scene previews and telemetry are synthetic and must not be presented as Cosmos or Isaac output. The real provider clients, authenticated GPU worker, trace-derived metrics, and deployment steps are documented in [docs/PRODUCTION.md](docs/PRODUCTION.md).

## Nebius Nemotron mode

Set these in `.env`:

```dotenv
GHOST_JUDGE_PROVIDER=nebius
NEBIUS_API_KEY=your_token_factory_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_SUPER_MODEL=nvidia/nemotron-3-super-120b-a12b
NEBIUS_ULTRA_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b
```

Use the exact model IDs currently shown in the Token Factory catalog. Each trial gets two Super passes. Confidence below 0.6 or category disagreement escalates to Ultra.

## Production adapter boundary

The pipeline defines three interfaces in `ghost_trials/adapters.py`:

1. `ScenarioGenerator` returns a structured hazard and artifact URL.
2. `Simulator` accepts that scenario and returns the stable `TrialMetrics` contract.
3. `TrialJudge` returns category, confidence, reasoning, and model tier.

Production implementations are included for Cosmos 3 Generator NIM/vLLM-Omni and the remote GPU job protocol. Store generated video, simulator recording, raw telemetry, judge inputs, and judge outputs under the trial ID. Production mode never silently falls back: it marks the trial `error` and retains partial evidence.

The Isaac job should accept at minimum:

```json
{
  "scenario_id": "scn_0091",
  "seed": 42,
  "embodiment": "UNITREE_G1_SONIC",
  "policy": "gr00t_n1d7_sonic",
  "structured_description": {}
}
```

It returns the `TrialMetrics` fields defined in `ghost_trials/models.py`. Metadata and hashes make an evaluation more traceable; they do not make it a formal certificate.

## GPU deployment kit

Everything that can be automated before account access is included:

- `deployment/cosmos.compose.yaml`: official Cosmos 3 Generator NIM with GPU reservation and readiness probe
- `deployment/worker.compose.yaml`: authenticated, GPU-pinned Isaac/SONIC job worker
- `scripts/bootstrap_gpu_host.sh`: Docker and NVIDIA Container Toolkit bootstrap for Ubuntu GPU hosts
- `scripts/install_robotics_stack.sh`: upstream GR00T/SONIC installation and public SONIC v1.1 model download
- `scripts/train_groot_sonic.sh`: task-policy fine-tuning from a processed `UNITREE_G1_SONIC` LeRobot dataset
- `scripts/checkpoint_digest.sh`: stable policy evidence digest
- `scripts/run_production.sh`: fail-closed preflight followed by dashboard startup

These scripts cannot create paid cloud accounts, accept licenses, fabricate demonstrations, or mint credentials. See [docs/PRODUCTION.md](docs/PRODUCTION.md) for the execution order.

## Architecture

```text
hazard prompt
     │
     ▼
ScenarioGenerator ──► Simulator ──► TrialJudge ──► evidence record
     │                    │              │                │
 Cosmos adapter       Isaac job     Nemotron API    dashboard/export
 local adapter        seeded local  fixed rubric
```

## Safety Score

| Outcome | Weight |
|---|---:|
| Avoided | 1.00 |
| Mitigated | 0.65 |
| Failed | 0.20 |
| Catastrophic | 0.00 |
| Insufficient evidence | Excluded; shown separately |

This is an experimental product metric, not a safety standard or a calibrated probability. Scoring uses `warehouse-evaluation-v3`; older records retain their original rubric and are not pooled with newer records. Falls/collisions and task completion are reported independently. Current proxy-based robot response measurements require review, not confident pass claims. Catastrophic causation is not established by the current runner contract.

See [evaluation methodology and remaining validation](docs/EVALUATION.md), [free-credit steps](docs/FREE_CREDITS.md), and [execution handoff](docs/EXECUTION_HANDOFF.md).

For pinned checkpoint access, the single-trial GPU acceptance command, reduced-traction support, and offline evidence verification, see [GPU acceptance and validation](docs/GPU_ACCEPTANCE.md). These tools do not provision a VM or turn a Token Factory API key into GPU access. The public development preview stays synthetic until an authorized operator configures and validates the external stack.

For the hosted frontend and backend proxy configuration, see [Netlify deployment](docs/NETLIFY.md). Netlify needs a public HTTPS FastAPI origin; model and GPU credentials stay on the backend services.

## License

MIT
