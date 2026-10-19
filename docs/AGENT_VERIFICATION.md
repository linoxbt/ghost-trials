# AI Agent Verification (bundled reference milestone)

Ghost Trials now has two verification domains in the existing Hunt lifecycle: `physical_ai` (the existing CPU MuJoCo/optional GPU path) and `ai_agent` (a controlled, CPU-only reference-agent harness). Legacy Hunts and Ghost Cases without a `domain` field still parse as Physical AI. The same authenticated `/hunts`, `/ghost-cases`, and regression routes persist and scope both domains by organization. Agent traces use the separate `/agent-trials/{id}` route because robot telemetry fields would misrepresent tool events.

## What actually executes

Only the checked-in `reference-vulnerable-v1`, `reference-corrected-v2`, and timeout-test `reference-hang-v1` targets are accepted. Each trial launches the selected reference agent in a bounded subprocess. The child sends tool requests over a line-delimited protocol; the **parent harness** authorizes them, controls the in-memory state, returns mock responses, and records the observed tool events. Available mocks are `notes.read`, `notes.write`, and a prohibited `admin.delete` request. Denied requests are recorded but never executed. Initial state contains `scratch_note` and an immutable `protected_record`. No production account, database, credential, or external API is contacted. Arbitrary paths, commands, uploaded Python, and customer executables are rejected. The harness sanitizes the child environment, limits CPU time, virtual memory, open files, output size and wall time, and kills the process group on timeout. These measures are operational limits **not a secure sandbox for untrusted code**; outbound network isolation and non-root execution are not guaranteed by this local reference runner. A future isolated runner is required before accepting untrusted targets on Railway or elsewhere.

## Oracle and search

The `agent-oracle-v1` assertions are `forbidden_tool_invocation`, `protected_state_unchanged`, and `required_task_completed`. Each assertion references a tool event, final state, or structured output. The selected verification objective chooses which assertion determines its verdict; other assertions remain visible as diagnostic observations. Outcomes distinguish verified success/failure from execution error. An agent timeout cannot become a verified failure. The reference search varies only supported attack variants 0–4 and pressure 0–2. Adaptive Hunts explore benign and adversarial inputs, repeat a verified failure with the same scenario/seed, then mutate the bounded pressure value. Trial count and wall-time budgets stop the Hunt. The search does not establish global robustness.

Trace records retain target/version, harness/oracle version, policy, initial and final state, input, untrusted tool response, seed, tool-call events, assertions, timestamps, output, and a canonical SHA-256 digest. Retrieval verifies the digest and recomputes the oracle. The hash detects alteration in the retained record; it is not an external attestation of process identity. Only a verified failed trace creates a Ghost Case. Exact replay is a justified claim only for these deterministic bundled agents; probabilistic model agents would require repeated statistical reproduction and pinned model/runtime provenance.

`POST /agent-trials/{id}/replay` re-executes the saved target and scenario. `POST /ghost-cases/{id}/regressions` with `{"target_id":"reference-corrected-v2"}` executes the revised reference target against the saved case. A `fixed_on_case` result means this one scenario passed its objective-specific deterministic oracle; it does not mean the revised agent is generally safe. Physical-AI replay and comparison paths are unchanged.

Nemotron is **not** called by the basic agent harness. An operator may explicitly request `POST /agent-trials/{id}/model-review` after a verified trace exists. The separate review calls the configured Nemotron Super model through Nebius Token Factory, requests explanation, exact trace references, contributing factors, remediation and regression suggestions, and rejects references that do not exist. The result is stored outside the evidence digest and cannot change the deterministic oracle verdict. The route fails closed when `GHOST_AGENT_MODEL_REVIEW_ENABLED`, credentials, live execution, provider-side spending confirmation, platform ceiling, or organization budget are missing. It reserves one bounded call using the existing model-review limit and never automatically retries a potentially billed attempt. `GET /agent-trials/{id}/model-review` is read-only. Provider credentials and paid inference are unnecessary for the basic Hunt.

## Local demonstration

From a CPU-only Linux checkout with Python 3.11+, `uv`, and project dependencies installed:

```bash
uv sync --frozen --extra dev
uv run python -m scripts.multidomain_demo --output data/multidomain-demo
uv run pytest -q
```

The command executes a real nine-trial MuJoCo Hunt with retained physics artifacts, verifies and replays a measured robot-controller failure, then executes a six-trial agent Hunt. It records a forbidden mock-tool request, verifies and reproduces the agent failure, and runs the corrected agent against the saved case. The JSON report names both cases and evidence outcomes. The script forcibly selects local CPU/no-paid-provider mode before importing the app and does not deploy anything. Use a fresh output directory for each demonstration.

The frontend's Hunt page now offers a domain selector. Agent Hunts show bounded variant coverage, trial sequence, trace inspector, deterministic assertions, case evidence, replay, and corrected-version comparison. Agent trial records do not enter the legacy Physical AI score. Existing Privy/Dynamic authentication, role checks, and organization ownership apply to all new routes. For a public deployment, keep the existing single-replica SQLite volume, HTTPS, authenticated access, and backups; do **not** enable arbitrary agent execution in that service.

To enable optional agent-trace review, set `GHOST_AGENT_MODEL_REVIEW_ENABLED=true` on the backend, retain the existing `NEBIUS_API_KEY`, `GHOST_LIVE_EXECUTION_ENABLED=true`, `GHOST_PROVIDER_SPENDING_CONTROLS_CONFIRMED=true`, a nonzero `GHOST_PLATFORM_BUDGET_CENTS`, and a signed-in organization's allocated budget. The shared `GHOST_CPU_MODEL_REVIEW_RESERVATION_CENTS`, token cap and timeout also bound this explicit call. First confirm credit-only usage or a real provider-side spending limit: a local reservation is not an external billing cap. No variable belongs in the frontend build. Railway does not need GPU for these server-side requests, but its own service charges and provider inference charges remain possible.

Future adapters for APIs, browsers, or arbitrary executable software are not implemented. The current controlled reference-agent milestone demonstrates the multi-domain verification contract without claiming a general security testing service.
