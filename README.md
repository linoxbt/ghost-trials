# Ghost Trials

Ghost Trials is an **experimental autonomous red-team platform for physical AI**. Give it a Unitree G1 policy and a task; it searches bounded physical conditions for failures, verifies the recorded evidence, reproduces findings, and replays saved Ghost Cases against a new checkpoint. It is not a safety-certification service. Provider integrations are implemented, but a genuine end-to-end GPU policy Hunt has not yet been demonstrated in this deployment.

This repository is the runnable product shell for the Nebius × NVIDIA Global AI Hackathon Physical AI track. It runs without GPU credentials using deterministic development adapters. Those adapters preserve the production contracts, so Cosmos generation and Isaac Lab-Arena jobs can replace them without changing the API or dashboard.

## Hackathon submission

The [Devpost submission package](docs/submission/README.md) contains the project overview, detailed [project story](docs/submission/PROJECT_STORY.md), field-by-field [organizer answers](docs/submission/ADDITIONAL_INFO.md), [demo script](docs/submission/DEMO_SCRIPT.md) and [evidence-status snapshot](docs/submission/EVIDENCE_STATUS.md). Personal details, numeric ratings, project-history confirmation and the public video URL require owner completion. The package distinguishes demonstrated model access from pending GPU/robot execution; it is not a submitted entry or proof of eligibility.

## Quick start

Requirements: Python 3.11+, Node 22+, npm, and `uv`.

```bash
cp .env.example .env
npm ci
npm run build:auth
uv sync --extra dev
uv run uvicorn ghost_trials.app:app --reload
```

Open <http://127.0.0.1:8000> for the animated landing page, `/docs` for documentation, or `/app/` for the Hunt workspace. The first development start seeds six synthetic trials. A local Hunt exercises the queue and search logic with synthetic data; it does not generate Cosmos video, execute a GPU policy, or produce verified Ghost Cases.

For a phone on the same network, run `make mobile`, determine this machine's LAN IP, and open `http://<LAN-IP>:8000` on the phone. Do not expose the development server directly to the public internet.

```bash
uv run pytest
```

Or use Docker:

```bash
docker compose up --build
```

## Current build

The [Ghost Hunt guide](docs/HUNT.md) documents supported worker controls, search phases, evidence admission, exact replay, regression, and current live-execution limits.

- Primary Hunt workflow: bounded adaptive/random/grid search, parameterized SONIC/Arena recipes, mutation, exact repeats, conditional empirical boundaries, persisted Ghost Cases, and compatible-checkpoint regression
- First-class authenticated `/hunts` and `/ghost-cases` API with organization isolation and paid-job admission on every candidate
- Hunt, Failures, Trials, Compare, and System workspace navigation; physical capture and manual tools remain under System → Advanced

- FastAPI API: `POST /scenarios`, `GET /trials`, `GET /trials/{id}`, `GET /safety-score`, and `WS /live`
- Persistent, typed scenario and evaluation records
- Seeded, replayable simulation metric adapter
- Versioned experimental rubric with evidence-aware incident reports, not demonstrated causal certification
- Optional Nebius Token Factory / Nemotron judge with two-pass disagreement detection and Ultra escalation
- Orange application interface with custom vector branding, collapsible sidebar, and accessible mobile hamburger navigation
- Separate Overview, Trial Runs, Scenario Library, Create Trial, Reports, System, and flight-record views
- Searchable/filterable trial records, live progress, and JSON evidence exports
- Compare runs with setup compatibility checks, metric deltas, and linked recording controls
- Evidence inspector with recorded incident timestamps, provenance, artifact manifests, and original judge interpretations
- Benchmark coverage split by policy/checkpoint, simulator, rubric, embodiment, and evidence origin
- Versioned score guardrails: synthetic, unverified, legacy, proxy-only, incomplete and uncertain evidence is excluded; collisions are not causal proof; eligible incompatible cohorts are not pooled
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

Production implementations are included for hosted Cosmos video generation, NIM/vLLM-Omni paths and the remote GPU job protocol. Store generated video, simulator recording, raw telemetry, judge inputs, and judge outputs under the trial ID. Production mode never silently falls back: missing resources produce an explicit `blocked` record and stage failures produce `error`, retaining produced artifacts where available. Configuration is not proof that these integrations have executed successfully.

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

## Experimental evaluation score

Synthetic demo records, unverified measurements, legacy rubrics, proxy-only measurements, incomplete artifacts, uncertain findings, and records without a live Nemotron review are excluded. A stored outcome or a configured provider is not execution proof. An unavailable score is `null`, not zero. Demo findings remain inspectable and prominently labeled. The legacy API field `/safety-score` remains for compatibility; it does not imply certification.

`GET /trials/ID/reproducibility` exports scenario/configuration, checkpoint identity, execution recipe, raw trace and response-video references, hashes, verification results, original judge assessment, and measurement/replay limitations. Artifact references require authorization; this JSON does not embed the video. `GET /demonstration-readiness` reports the narrow recorded-trial milestone, never competition eligibility or hardware attestation.

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

## Production hardening

See [private deployment and readiness gates](docs/PRODUCTION_READINESS.md) for
authentication, persistent jobs/evidence, backups, monitoring and deployment.
This implementation supports individual Privy email/Google identities and
organization-isolated workspaces in one API process. Team invitations, role
changes, session revocation, tenant-filtered media/live updates, and atomic
execution-admission budgets are implemented. See [account setup](docs/AUTHENTICATION.md).
Real GPU execution and independent expert validation remain required before
promotion; these are not demonstrated by synthetic previews or unit tests.

## Physical robot recordings

The dashboard includes **Physical recordings** at `/app/#/physical`. Prepare a
private capture plan while hardware access is pending; unknown identity and
weights remain blank. Once an on-site operator validates a compatible G1 29-DOF
setup, the read-only observer can record camera video, DDS joint/IMU feedback,
and commands from an externally running policy. The API provides resumable,
hash-checked uploads, full video decoding, telemetry validation and explicit
budget-gated Nemotron judging. It has no motor-control or hazardous-action routes.

See [the physical robot handoff](docs/PHYSICAL_ROBOT.md). Hardware provenance is
operator-declared, command-change timing remains a proxy, and real hardware
testing/calibration and independent review have **not** been completed.
