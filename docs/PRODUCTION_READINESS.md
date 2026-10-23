# Private production deployment and promotion gates

> **Scope note (23 October 2026):** this page covers the generic self-hosted Docker/Caddy deployment. The current hosted release runs a single Docker container behind Caddy on a VPS (backend, `https://backend.ghosttrials.site`) and Netlify (frontend, `https://ghosttrials.site`); see [CPU_MIGRATION.md](CPU_MIGRATION.md) and [NETLIFY.md](NETLIFY.md).

This is an **organization-isolated, single-API-process** deployment. It is not a
scale-out SaaS, an accredited safety certification, or proof of real GPU
execution. No cloud resources are created by these commands. Existing provider
adapters remain fail-closed when required resources are absent.

## What is implemented

| Area | Implementation | External or unverified prerequisite |
| --- | --- | --- |
| Real execution | Existing Cosmos and G1 adapters; read-only `/ops/providers`; checkpoint checks; worker acceptance command; mandatory evidence capture and recomputation before scoring | Authorized model endpoints, GPU allocation, compatible fine-tuned weights, and an actual full run |
| Stable hosting | `deployment/secure.compose.yaml`, restart policies, persistent volumes, Caddy HTTPS, Netlify auth/ops proxy routes | Permanent domain/DNS, host, original Netlify project access and resolved usage limit |
| Access and cost exposure | Privy or Dynamic.xyz email/Google identities, hashed revocable sessions, private workspace invitations and roles, tenant-filtered records/media/live events, operator-only infrastructure controls, atomic org/platform admission reservations, default-off paid execution | Enable methods in the selected identity provider; provider-side budget enforcement and VM shutdown policy. Admission reservations are not actual billing or a monetary cap |
| Durable data/jobs | SQLite WAL transactions, atomic acceptance/idempotency, persisted serialized queue, exclusive process lease, queued cancellation, crash recovery, private S3 replica option, bounded backup/restore | Off-host backup destination, retention configuration, restore rehearsal on the deployment host |
| Validation | Independent metric recomputation; full video decoding; reference-label audit; minimum hazard/seed coverage; fail-closed promotion CLI | Real captured evidence, independent experts, calibrated metrics, matched policy baselines and transfer validation |
| Operations | Private status/audit/readiness endpoints, request IDs and redacted logs, polling/webhook monitor, locked dependencies, CI and manual frontend deployment workflow | Alert destination, deployment secrets, operational ownership, production load/failure testing |

## 1. Prepare access, without changing the existing preview

```bash
uv sync --frozen --extra storage
uv run python -m ghost_trials.access_setup
```

This creates `deployment/private/access.env` with distinct role tokens, permission
0600, and does not print them or overwrite existing tokens. Use the admin token
from that private file to sign in at `/auth/login`. Distribute viewer/operator
tokens only through a secure channel. These are shared platform/legacy roles,
not individual accounts. Customers authenticate through the selected provider and receive separate
organization-scoped workspaces; organization admins never gain platform-operator
access. See [AUTHENTICATION.md](AUTHENTICATION.md) for setup and membership rules.
Replace a compromised token in the private file and restart the API and monitor;
existing cookies tied to that token become invalid. Changing the admin token
invalidates every signed legacy session. Legacy token logout removes the browser
cookie, not a stolen copy. Individual provider sessions are persisted as hashes and
revoked server-side on logout/member removal. Use short session lifetimes.

## 2. Configure a permanent deployment

Complete `deployment/private/production.env` from
`deployment/production.env.example` without replacing existing credentials.
The secure Compose file loads `access.env` after `production.env`.

Required infrastructure:

- An authorized host with Docker and permanent backend DNS pointed at it.
- Incoming TCP 80/443 and UDP 443 if desired; **do not expose API port 8000**.
- `GHOST_DOMAIN`, `ACME_EMAIL`, and exact HTTPS origins in
  `GHOST_ALLOWED_ORIGINS`, including both backend and frontend origins.
- Existing Cosmos/worker/Nebius settings and matching checkpoint identity for
  `GHOST_MODE=production`. A protected synthetic preview can use `GHOST_MODE=local`
  with all three providers set to `local`, clearly marked as development.

```bash
docker compose --env-file deployment/private/production.env -f deployment/secure.compose.yaml config --quiet
docker compose --env-file deployment/private/production.env -f deployment/secure.compose.yaml up -d --build
```

Exactly one API worker is supported and enforced with a database file lease.
The database and artifacts live on the `ghost-production` volume. The API runs
as UID 10001 with a read-only root filesystem. Existing externally mounted data
must be writable by that UID. Caddy configures HTTPS for the domain; DNS and
certificate-challenge reachability must be supplied by the operator. See the
[Caddy HTTPS requirements](https://caddyserver.com/docs/automatic-https).

Netlify needs **only** `GHOST_BACKEND_ORIGIN=https://your-permanent-backend-domain`.
Never put model keys or organization role tokens in the frontend build. The
frontend is a public static shell; its API data and generated artifacts require
authentication. Set up the `production` GitHub environment with
`NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` secrets and a `GHOST_BACKEND_ORIGIN` variable
for the manual deployment workflow. This cannot repair missing Netlify account
access or a platform usage limit.

## 3. Verify resources and explicitly enable paid submissions

```bash
uv run python -m ghost_trials.preflight
uv run python -m ghost_trials.gpu_acceptance
```

These are readiness checks, not execution proof. Confirm provider-side spending
limits and a GPU shutdown policy first. Then configure positive
`GHOST_PLATFORM_BUDGET_CENTS` and `GHOST_LIVE_JOB_RESERVATION_CENTS`, set
`GHOST_PROVIDER_SPENDING_CONTROLS_CONFIRMED=true`, allocate each organization's
budget using platform-only `PUT /ops/organizations/{id}/budget`, and set
`GHOST_LIVE_EXECUTION_ENABLED=true`. Restart the API. Only authenticated
operators/admins can submit. `GHOST_MAX_PENDING_JOBS`, `GHOST_MAX_JOBS_PER_DAY`,
`GHOST_MAX_REQUESTS_PER_MINUTE` and `GHOST_MODEL_MAX_TOKENS` bound application
usage, **not dollar cost or idle GPU charges**. The minimum deployment has no
automatic GPU provisioning or guaranteed remote cancellation.

Every paid submission reserves budget atomically with queue acceptance. New
organizations start with zero allocation. Failed/cancelled jobs are not refunded
automatically because external charges may already have occurred. Reservations
are conservative admission accounting, not a provider-billed dollar cap: choose
an upper bound appropriate to the pipeline, and enforce real limits externally.
The provider-confirmation setting is an operator attestation, not automatic proof
that cloud billing is capped.

For retried submissions, reuse the same `Idempotency-Key` header. Keys are scoped
to the active organization. An identical
request returns its original trial; a conflicting payload returns 409. Queued
jobs can be cancelled through `POST /trials/{id}/cancel`. Active jobs return 409:
an API timeout does not prove the remote GPU has stopped. Interrupted jobs are
marked for review, never automatically retried. Successful phase recovery is
not implemented: the safe default is to inspect the worker before resubmission.

## 4. Retain and independently review evidence

Worker recordings, telemetry, recipe, requested scenario and verifier reports
are copied into private durable storage before judging. Sizes, hashes and
worker origin are checked; bearer tokens are not forwarded to artifact URLs.
Trial media URLs point at authenticated `/generated` paths instead of expiring
worker URLs. Optional S3 replication uses content-addressed keys, private access
and server-side encryption. Configure a private bucket, SDK credentials,
`GHOST_ARTIFACT_BUCKET` and `GHOST_S3_ENDPOINT` where required. Configure bucket
versioning, lifecycle/retention and service permissions separately. S3 is a
replica here, not an automatic failover or primary read path. Review the
[object-write API](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).

Run two distinct seeds for each supported hazard, capture a compatible baseline
and candidate, and export completed trials from the workspace. Independent
reviewers supply adjudicated labels using this format:

```json
[
  {
    "trial_id": "trl_actual_id",
    "score_category": "failed",
    "reviewer": "external-reviewer-identifier",
    "rationale": "Specific observations from the recording and telemetry."
  }
]
```

```bash
uv run python -m ghost_trials.review_audit evaluation.json reviews.json
uv run python -m ghost_trials.release_gate --reviews reviews.json
```

The offline gate requires six real-evidence trials, all three hazard types with
two distinct seeds, expected checkpoint identity, verified bundles, full video
decoding and reviewed labels without unresolved disagreements. It does not
verify reviewer independence, authenticate GPU execution, establish causal
safety, calibrate the rubric, or validate transfer to a real robot. Experts must
evaluate the response/clearance proxies and matched baseline results. Passing
this minimum engineering gate must not be advertised as recognized certification.

## 5. Back up and rehearse recovery

Use the admin-only `POST /ops/maintenance` with JSON `{"enabled": true}` to pause
all new submissions, then finish/cancel pending jobs before a consistent evidence
backup. This pause is persisted across restarts. The backup CLI refuses to run
unless submissions are paused and no jobs are pending. Resume using the same
endpoint with `{"enabled": false}` after verifying the backup. Keep it outside the
primary host and protect it: it includes prompts and evidence, though not `.env`.
The SQLite online backup mechanism creates a consistent DB snapshot; see
[Python SQLite documentation](https://docs.python.org/3/library/sqlite3.html).

```bash
uv run python -m ghost_trials.backup create data/backups/backup-unique.tgz
uv run python -m ghost_trials.backup restore data/backups/backup-unique.tgz data/restore-drill --sha256 DIGEST_FROM_BACKUP_REPORT
```

The CLI must use the same database/artifact paths as the live API. For the secure
Compose deployment, run it **inside the dashboard container** instead of pointing
a host CLI at a separate local preview database:

```bash
docker compose --env-file deployment/private/production.env -f deployment/secure.compose.yaml exec dashboard python -m ghost_trials.backup create /data/backups/backup-unique.tgz
docker compose --env-file deployment/private/production.env -f deployment/secure.compose.yaml exec dashboard python -m ghost_trials.backup restore /data/backups/backup-unique.tgz /data/restore-drill --sha256 DIGEST_FROM_BACKUP_REPORT
```

Restore refuses existing destinations, traversal/symlink entries, digest
mismatches and oversized archives, then checks database integrity. A restore
drill does not replace the live database. To recover live service, stop the API,
restore to a new directory/volume, inspect evidence and job state, configure the
new data paths and start one API instance. Do not overwrite a running database.

## 6. Operate and test before promotion

- `/health`: public process liveness, not GPU readiness.
- `/ready`: authenticated DB/queue readiness, not model execution proof.
- `/ops/status`: admin-only health, job counts, configured quotas and active job.
- `/ops/audit`: platform-operator-only global history. Organization admins see
  individual actor IDs in `/organizations/current/audit`, limited to their workspace.
- `/ops/maintenance`: admin-only durable pause/resume of new submissions.
- `/ops/providers`: admin-only read-only endpoint readiness checks.
- Monitor service: checks API/queue/database health, failed-job counts and disk
  space every 30 seconds; deduplicates alerts and retries failed webhook delivery.
  Set `GHOST_ALERT_WEBHOOK` to an endpoint accepting JSON. It is not a hosted
  pager or a metrics platform; store/route alerts with your operations tooling.

CI runs unit/integration tests, physics checks, Netlify build and image build.
GPU/model tests remain explicitly external and do not run on ordinary CI runners.
Before inviting paying users, rehearse process restart, backup restore, request
retries, quota exhaustion, malformed evidence, unreachable endpoints, alert
delivery and realistic concurrent read traffic. Review privacy/retention terms,
service SLOs and professional safety claims. Do not enable multiple API replicas.
