# Ghost Trials

*Find what breaks. Prove why. Prevent it from happening again.*

Ghost Trials is an **experimental autonomous failure-discovery and verification platform**. It supports the existing Physical AI workflow and a controlled AI-agent reference domain. Give it an executable target and a task; it searches bounded conditions for failures, verifies recorded evidence, reproduces findings, and replays saved Ghost Cases against another version. It is not a safety-certification service. The default robotics path runs real headless MuJoCo physics on CPU. The agent path executes only bundled reference agents with in-memory mock tools; arbitrary customer code remains blocked. The original Unitree G1/SONIC/Isaac path remains optional and has not been demonstrated end to end in this deployment.

For the implemented two-domain contract, trust boundaries, oracle methodology, replay limitations, and one-command CPU demonstration, see [AI Agent Verification](docs/AGENT_VERIFICATION.md).
The [audit remediation record](docs/AUDIT_REMEDIATION.md) covers the code-level fixes and limits; its hosted-release snapshot predates the self-hosted deployment described below.

The CPU task uses a two-axis gantry arm to position a free block on a tabletop. MuJoCo advances articulation, contacts, gravity and friction; the controller runs at every physics step. The Hunt varies actual model/controller parameters, adapts to measured outcomes, retains trace-derived evidence, and can reproduce or regress a failure. A separately gated NVIDIA Nemotron review through Nebius Token Factory can interpret every verified CPU trial; model failure never changes the measured outcome. NVIDIA/Nebius services are not dependencies of CPU physics. The legacy `local` adapter remains synthetic and is development-only.

## Hosted release status (checked 23 October 2026)

The frontend is on Netlify at [ghosttrials.site](https://ghosttrials.site); the FastAPI CPU backend runs in Docker behind Caddy on a single self-hosted VPS at `https://backend.ghosttrials.site`, and Netlify proxies API routes to it. On 22 October 2026 the backend moved from Railway to a self-hosted VPS after Railway suspended services; the database started fresh. The [live health response](https://ghosttrials.site/health) reports `api_contract: multidomain-v1` with MuJoCo CPU execution. The Netlify site serves the same frontend files as `main`, and its `/agent-trials` proxy returns `401` without a session, confirming the protected two-domain route is reachable. These are deployment and route checks, **not** a signed-in end-to-end production Hunt or a new live Nemotron review; treat the hosted site as validated only after a signed-in two-domain smoke test passes. The previously exposed Privy secret was rotated on 23 October; the backend never used it (it verifies sign-in tokens against Privy's public keys).

## Hackathon submission

The [Devpost submission draft](submission.md) describes both demonstrated local domains and the current partial hosted release. Regenerate the [PDF dossier](submission.pdf) from `submission.md` (`scripts/render_submission.py`) before attaching it. Personal details, numeric ratings, project-history confirmation, a signed-in production demo and the public video URL still require owner completion. Earlier planning drafts remain under [docs/submission](docs/submission/README.md). None of these documents is a submitted entry or proof of eligibility.

## Quick start

Requirements: CPU-only Linux, Python 3.11+, Node 22+, npm, and `uv`. See [CPU deployment and limitations](docs/CPU_MIGRATION.md).

```bash
cp .env.example .env
npm ci
npm run build:auth
uv sync --extra dev
uv run python -m scripts.run_cpu
```

If you already have a private `.env` selecting the GPU/production providers, leave it intact and start the CPU mode explicitly with `uv run python -m scripts.run_cpu`.
Direct `uvicorn` startup without authentication now fails closed. The loopback-only `scripts.run_cpu` command explicitly enables unauthenticated development mode when no identity provider or role token is configured. Never enable `GHOST_UNAUTHENTICATED_LOCAL_DEV` on a public server.

Open <http://127.0.0.1:8000> for the landing page, `/docs` for documentation, or `/app/` for the Hunt workspace. Choose **CPU MuJoCo tabletop**, an executable gantry controller, and **Release the Ghost**. Completed CPU trials contain measured telemetry and a state-derived trajectory SVG, not a fabricated robot video. With the CPU defaults in `.env.example`, no GPU, CUDA, API key, or paid service is needed. An existing private `.env` may override those defaults; consult its provider settings before starting.

Run a repeatable full API/worker/evidence check (nine bounded grid trials, exact replay, alternate-controller regression):

```bash
uv run python -m scripts.cpu_smoke --strategy grid --trials 9 --output data/cpu-validation
```

To verify **both** implemented domains in one CPU-only command, run `uv run python -m scripts.multidomain_demo --output data/multidomain-demo`. This executes actual MuJoCo physics and a bundled agent process, then verifies, replays, and compares their saved failures. It neither deploys nor calls a paid provider.

At the 23 October local verification snapshot, the full Python suite passed **229 tests** and all eight Playwright browser checks passed (`npm run check:ui`), including a mobile-sized Hunt/agent-trace flow. Those checks do not establish hosted sign-in, public frontend routing, physical G1 execution, or independent robotics review.

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
- Hunt, Failures, Trials, and Compare workspace navigation; team, physical capture, benchmarks, reports and manual tools are under Account
- A compact sign-in screen and an Account page for profile-name updates, workspace identity, sign-in settings, and sign-out; provider credentials and email remain with the identity provider
- AI-agent Hunts execute only allowlisted bundled reference targets with parent-mediated mock tools, versioned deterministic assertions, retained tool traces, exact reference replay, and case-specific corrected-target regression; untrusted customer executables are blocked

- FastAPI API: `POST /scenarios`, `GET /trials`, `GET /trials/{id}`, `GET /safety-score`, and `WS /live`
- Persistent, typed scenario and evaluation records
- Seeded, replayable MuJoCo execution with trace-derived metrics; the separate `local` adapter is synthetic development data
- Versioned experimental rubric with evidence-aware incident reports, not demonstrated causal certification
- Optional Nebius Token Factory / Nemotron review: one gated Super call for an artifact-verified CPU trial or agent trace; the separate legacy GPU judge supports two-pass disagreement detection and Ultra escalation
- Orange application interface with custom vector branding, collapsible sidebar, and accessible mobile hamburger navigation
- Separate Overview, Trial Runs, Scenario Library, Create Trial, Reports, Account, and flight-record views
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

Use the exact model ID shown in the current Token Factory catalog. An operator must also allocate the signed-in organization a budget: with an operator token configured, through `/ops/organizations/{organization_id}/budget` on the backend origin; otherwise with `python -m ghost_trials.budget set <organization_id> <cents>` where the API's database lives (for the hosted VPS, inside the container: `docker exec -u 10001 -w /app ghost-trials-api-1 /app/.venv/bin/python -m ghost_trials.budget list`). Each verified trial reserves the review amount automatically, so a 200-cent ceiling covers about 20 reviews in total. The 200-cent platform limit is an **admission reservation ceiling, not a billing guarantee**; confirm credit-only use or a provider-side hard limit before enabling live calls. No automatic Ultra escalation occurs in this CPU path. A missing key, budget exhaustion, timeout or invalid model citation leaves the measured MuJoCo trial complete and visibly marks its separate model review unavailable or failed. The older GPU path still uses the two-pass Super/Ultra judge.

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

See [GPU-path evaluation methodology](docs/EVALUATION.md) (the CPU path is in [CPU_MIGRATION.md](docs/CPU_MIGRATION.md)), [free-credit steps](docs/FREE_CREDITS.md), and [execution handoff](docs/EXECUTION_HANDOFF.md).

For pinned checkpoint access, the single-trial GPU acceptance command, reduced-traction support, and offline evidence verification, see [GPU acceptance and validation](docs/GPU_ACCEPTANCE.md). These tools do not provision a VM or turn a Token Factory API key into GPU access. Local CPU MuJoCo execution is real simulation; the optional G1/SONIC GPU path still requires its own acceptance run. The hosted Netlify site is connected to the self-hosted CPU backend; verify its health and sign-in flow before presenting it as a working demo.

For the hosted frontend and backend proxy configuration, see [Netlify deployment](docs/NETLIFY.md). Netlify needs a public HTTPS FastAPI origin and the new `/agent-trials` proxy route before the agent UI can work there; model and GPU credentials stay on the backend services.

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
