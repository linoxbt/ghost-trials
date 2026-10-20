# Ghost Trials

*Find what breaks. Prove why. Prevent it from happening again.*

Ghost Trials is an **experimental autonomous failure-discovery and verification platform**. It supports the existing Physical AI workflow and a controlled AI-agent reference domain. Give it an executable target and a task; it searches bounded conditions for failures, verifies recorded evidence, reproduces findings, and replays saved Ghost Cases against another version. It is not a safety-certification service. The default robotics path runs real headless MuJoCo physics on CPU. The agent path executes only bundled reference agents with in-memory mock tools; arbitrary customer code remains blocked. The original Unitree G1/SONIC/Isaac path remains optional and has not been demonstrated end to end in this deployment.

For the implemented two-domain contract, trust boundaries, oracle methodology, replay limitations, and one-command CPU demonstration, see [AI Agent Verification](docs/AGENT_VERIFICATION.md).
The latest code-level audit and unresolved release gates are in [Audit remediation status](docs/AUDIT_REMEDIATION.md).

The CPU task uses a two-axis gantry arm to position a free block on a tabletop. MuJoCo advances articulation, contacts, gravity and friction; the controller runs at every physics step. The Hunt varies actual model/controller parameters, adapts to measured outcomes, retains trace-derived evidence, and can reproduce or regress a failure. A separately gated NVIDIA Nemotron review through Nebius Token Factory can interpret every verified CPU trial; model failure never changes the measured outcome. NVIDIA/Nebius services are not dependencies of CPU physics. The legacy `local` adapter remains synthetic and is development-only.

## Hackathon submission

The [Devpost submission draft](submission.md) describes the local AI-agent milestone, but the [judge-facing PDF dossier](submission.pdf) predates it and must be refreshed before submission. Personal details, numeric ratings, project-history confirmation, the signed-in production demo and public video URL still require owner completion. Earlier planning drafts remain under [docs/submission](docs/submission/README.md). None of these documents is a submitted entry or proof of eligibility.

## Quick start

Requirements: CPU-only Linux, Python 3.11+, Node 22+, npm, and `uv`. See [CPU deployment and limitations](docs/CPU_MIGRATION.md).

```bash
cp .env.example .env
npm ci
npm run build:auth
uv sync --extra dev
uv run uvicorn ghost_trials.app:app --reload
```

If you already have a private `.env` selecting the GPU/production providers, leave it intact and start the CPU mode explicitly with `uv run python -m scripts.run_cpu`.

Open <http://127.0.0.1:8000> for the landing page, `/docs` for documentation, or `/app/` for the Hunt workspace. Choose **CPU MuJoCo tabletop**, an executable gantry controller, and **Release the Ghost**. Completed CPU trials contain measured telemetry and a state-derived trajectory SVG, not a fabricated robot video. With the CPU defaults in `.env.example`, no GPU, CUDA, API key, or paid service is needed. An existing private `.env` may override those defaults; consult its provider settings before starting.

Run a repeatable full API/worker/evidence check (nine bounded grid trials, exact replay, alternate-controller regression):

```bash
uv run python -m scripts.cpu_smoke --strategy grid --trials 9 --output data/cpu-validation
```

To verify **both** implemented domains in one CPU-only command, run `uv run python -m scripts.multidomain_demo --output data/multidomain-demo`. This executes actual MuJoCo physics and a bundled agent process, then verifies, replays, and compares their saved failures. It neither deploys nor calls a paid provider.

For a phone preview, use an authenticated HTTPS reverse proxy or tunnel and set `GHOST_PUBLIC_DEPLOYMENT=true` with individual sign-in and the exact HTTPS frontend origin. `make mobile` refuses a non-loopback bind without those safeguards. `make dev` and the default Docker Compose port bind to host loopback only; never expose an authentication-disabled development server to the LAN or internet.

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

The default `cpu` mode executes MuJoCo physics. The separate `local` mode remains an intentionally synthetic development adapter and its outputs must not be presented as MuJoCo, Cosmos, or Isaac output. Optional hosted providers and the GPU worker are documented in [docs/PRODUCTION.md](docs/PRODUCTION.md).

## Optional Nemotron review of CPU trials

The default CPU Hunt remains free of paid inference. To request one Nemotron Super interpretation per **artifact-verified** CPU trial, configure the backend only:

```dotenv
GHOST_MODE=cpu
GHOST_JUDGE_PROVIDER=cpu
GHOST_CPU_MODEL_REVIEW_ENABLED=true
NEBIUS_API_KEY=your_token_factory_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_SUPER_MODEL=nvidia/nemotron-3-super-120b-a12b
GHOST_LIVE_EXECUTION_ENABLED=true
GHOST_PROVIDER_SPENDING_CONTROLS_CONFIRMED=true
GHOST_PLATFORM_BUDGET_CENTS=200
GHOST_CPU_MODEL_REVIEW_RESERVATION_CENTS=10
```

Use the exact model ID shown in the current Token Factory catalog. An operator must also allocate the signed-in organization a budget through the existing `/ops/organizations/{organization_id}/budget` route. The 200-cent platform limit is an **admission reservation ceiling, not a billing guarantee**; confirm credit-only use or a provider-side hard limit before enabling live calls. No automatic Ultra escalation occurs in this CPU path. A missing key, budget exhaustion, timeout or invalid model citation leaves the measured MuJoCo trial complete and visibly marks its separate model review unavailable or failed. The older GPU path still uses the two-pass Super/Ultra judge.

Run one retained operator acceptance trial before turning on review for customer workspaces. The first command executes actual MuJoCo physics and verifies evidence without a paid call. The second makes at most one bounded Super call **only after** the operator confirms credit-only billing or a provider-side hard limit; the local 10-cent reservation is not an external billing cap:

```bash
uv run --extra physics python -m scripts.cpu_live_review --output /tmp/ghost-cpu-acceptance
uv run --extra physics python -m scripts.cpu_live_review --output /tmp/ghost-cpu-nebius-acceptance --env-file /path/to/private/.env --live-nebius --confirm-provider-limit
```

Use a new output directory for each command. Both save their SQLite record and raw evidence. `scripts/export_cpu_reference.py` produced the public reference bundle under `static/reference/gantry-v1/` from a separately executed, trace-validated CPU trial. The overview labels this reference as outside the signed-in organization's results; a new user can launch a guided six-trial physics Hunt to populate their own workspace.

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
 CPU task            MuJoCo CPU      measured rubric  trace/SVG/export
 Cosmos adapter      Isaac job       Nemotron API    optional GPU path
 local adapter       seeded local    fixed rubric    synthetic dev only
```

## Experimental evaluation score

Synthetic demo records, unverified measurements, legacy rubrics, proxy-only measurements, incomplete artifacts, and uncertain findings are excluded. CPU trials use the versioned, measured `cpu-object-positioning-v1` rubric; any optional Nemotron interpretation is stored separately and shown only when it actually completed. GPU-path trials require the configured live judge. A stored outcome or a configured provider is not execution proof. An unavailable score is `null`, not zero. The legacy API field `/safety-score` remains for compatibility; it reports tested task success for compatible verified CPU trials and does not imply certification.

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

For pinned checkpoint access, the single-trial GPU acceptance command, reduced-traction support, and offline evidence verification, see [GPU acceptance and validation](docs/GPU_ACCEPTANCE.md). These tools do not provision a VM or turn a Token Factory API key into GPU access. Local CPU MuJoCo execution is real simulation; the optional G1/SONIC GPU path still requires its own acceptance run. The hosted Netlify preview is connected to a Railway CPU backend; verify its health and sign-in flow before presenting it as a working demo.

For the hosted frontend and backend proxy configuration, see [Netlify deployment](docs/NETLIFY.md). Netlify needs a public HTTPS FastAPI origin; model and GPU credentials stay on the backend services.

## License

MIT

## Production hardening

See [private deployment and readiness gates](docs/PRODUCTION_READINESS.md) for
authentication, persistent jobs/evidence, backups, monitoring and deployment.
This implementation supports individual Privy or Dynamic.xyz email/Google identities and
organization-isolated workspaces in one API process. Team invitations, role
changes, session revocation, tenant-filtered media/live updates, and atomic
execution-admission budgets are implemented. See [account setup](docs/AUTHENTICATION.md).
CPU MuJoCo trials can now run and pass trace/metric integrity checks without GPU access. Independent robotics expert review and real-world validation are still absent; CPU evidence is simulation evidence, not hardware attestation. The optional G1/SONIC GPU path still requires its own live acceptance run.

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
