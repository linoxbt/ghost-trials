# Audit remediation status — 20 October 2026

This is a code-level remediation record, not production approval or safety certification. The executed checks are listed below. No paid inference, external deployment, or physical-robot test was performed during this remediation.

## Fixed and verified in this branch

| Finding | Resolution | Verification |
| --- | --- | --- |
| Protected-write attempts could pass the unsafe-mutation oracle | Versioned oracle v2 records attempted protected writes separately from actual state changes | Executable reference-agent regression test |
| Task completion accepted the wrong copied value | The oracle now compares the received value, executed write, final state, and structured completion | Executable wrong-value regression test |
| Local agent Hunts inherited paid GPU admission | Local reference-agent admission is separate from physical-provider spending checks; global daily quota remains | API test with Cosmos/Isaac selected and paid execution disabled |
| Ineffective pressure mutations inflated agent coverage | Pressure varies only variant 2; other mutations use distinct effective scenarios | Bounded-mutation test |
| Saved agent versions did not pin executable source/runtime | New traces retain checked-in source digest and Python runtime identity; replay/regression reject a mismatch | Provenance test and executable replay/regression test |
| Agent target records had no owner-facing registration | Allowlisted registration and tenant-scoped target/trial listing were added; arbitrary customer executables remain blocked | API and tenant-isolation tests |
| Execution errors looked like verified outcomes | Integrity of an error record is displayed separately from verified success/failure evidence | API regression test and updated trace UI |
| Manual replay did not update Ghost Case reproduction | Agent repeats are appended to cases; physical replay relations are persisted and recomputed from completed evidence | Agent API test and actual CPU two-domain demonstration |
| Saved cases could keep a stale verified/reproducible label after artifact tampering | Physical case retrieval rechecks retained baseline and repeat bundles; agent cases recompute repeat validity from stored traces | CPU artifact-tampering test and agent repeat-tampering test |
| Public CPU deployment could be inadvertently launched without sign-in | Railway environment and container entrypoint enforce public-auth configuration; development and Compose bind to host loopback by default | Public-auth configuration tests; container/host configuration review |
| Health check could report success with a stopped worker | Public `/health` now requires the job runner and database to respond | API regression test |
| Agent trials were absent from the main Trials view | Tenant-scoped history and trace exports were added; active Hunt view uses a focused poll | Mobile browser smoke |
| Database domain listing scanned all tenants in Python | SQLite organization index and filtered query were added; schema setup is not rerun on every connection | Full test suite and tenant-isolation tests |
| Netlify omitted the exact `/agent-trials` route | The frontend proxy now includes agent trials and demonstration readiness; a generated-route test prevents recurrence | `tests/test_netlify_routes.py` |
| A saved agent trace without source/runtime pinning could be rehashed into a verified state | Current verification requires the registered target version, source digest, and runtime identity; legacy records stay readable but unverified | Executable legacy-record test and agent API suite |
| Cached Nemotron review could outlive changed evidence | Review reads and reuse now require current trace verification and matching evidence digest | Agent review and trace API tests |
| Score and trial APIs trusted stale artifact-verification flags | Reporting, comparison, benchmark and Hunt outcome paths recheck retained simulator artifacts and use a downgraded copy when integrity fails | Actual MuJoCo bundle tampering and CPU/Hunt tests |
| CPU controller digest omitted implementation code | New CPU evidence records pin a controller/worker source digest; the public reference bundle was regenerated from actual MuJoCo execution | CPU verifier, physics, reference and replay tests |
| GPU “exact replay” could use a changed checkpoint | Completed GPU replays require the configured checkpoint and currently verified baseline evidence to match; blocked runs remain retriable but are not completed evidence | Replay API tests |
| Direct Uvicorn startup could default to unauthenticated admin | No-auth startup requires an explicit local-development flag; public/Railway/production modes reject that flag | Startup auth tests; existing account/API suites |
| Agent Hunt resume and alternate-target regression controls were incomplete | Agent Hunt now exposes the resume action; saved cases choose a different bundled target even when the baseline is corrected-v2 | Mobile browser smoke |
| Frontend release could pair new UI with an old backend | `/health` declares the multidomain API contract; the Netlify workflow checks that contract and required routes before publishing | API test, route test, workflow inspection |

Old agent records remain readable. Records without source/runtime pinning or using oracle v1 are marked `legacy_unverified` and cannot inherit v2 validation or be replayed as source-pinned evidence. The old records are not deleted or silently upgraded.

## Demonstrated locally

- The complete Python suite passed **193 tests** after the new fail-closed startup rule and fixture corrections. It includes actual MuJoCo execution and checked-in reference-agent subprocesses; fixtures and contract tests are not evidence of a physical G1 run.
- `uv run --frozen python -m scripts.multidomain_demo --output <fresh-directory>` executed both domains, verified retained evidence, and compared distinct controllers/agent versions. The final smoke script now requires two matching physical replays before reporting a reproducible case; the standalone CPU smoke test passed that stricter check.
- `PLAYWRIGHT_MODULE=/root/datatruth/node_modules/playwright node scripts/check_agent_frontend.cjs` exercised the authenticated-disabled **local** mobile-sized Hunt, trace, case, and regression flow. It does not validate public sign-in or the deployed release.

## Open release gates and limitations

1. **Credential rotation — release blocker.** A Privy secret was previously exposed in conversation. The app owner must revoke/rotate it in Privy and replace the private backend environment value. Do not put the new secret in chat, Git, frontend variables, or a demo artifact. This cannot be completed by a repository patch.
2. **Hosted validation — release blocker.** The existing Railway production service is healthy but still deploys `main` commit `990454e` from 18 October 2026; this branch and its Netlify route fix are not live. This checkout is not linked to the Railway project. The new frontend deploy gate intentionally rejects the old backend contract. Verify production auth, a fresh signed-in Hunt, replay, artifact access, quotas, health, backups, and rollback after an authorized coordinated release before calling it production-ready.
3. **External-model and robotics scope.** No new paid Nebius call, live Cosmos generation, Isaac/G1/SONIC trial, arbitrary customer-agent execution, or physical robot measurement was run here. The CPU MuJoCo and bundled-agent paths are the demonstrated scope. The reference-agent subprocess is not a secure isolation boundary for untrusted customer code.
4. **Independent trust.** Hashes, source pinning, and metric recomputation detect several inconsistencies but are not hardware attestation or independent expert review.
5. **Competition media.** The owner must record and publish a genuine <=3-minute demonstration with the required key modules; existing illustrations are not execution footage.
6. **Versioned evidence migration.** Saved pre-pinning CPU records remain readable but cannot be reverified against a changed controller source. This is intentional: the original executable bytes were not retained. The public reference was regenerated; customer records require a fresh execution to obtain current source-pinned evidence.

Do not publish a production-readiness claim until the release blockers are closed and recorded with evidence.

## Second audit — 23 October 2026

A second independent review (backend, frontend, deployment) found no Critical issues. Each fix below has a regression test or browser check.

| Finding | Resolution |
| --- | --- |
| A flood of junk sign-in tokens could lock everyone out (platform-wide attempt limit checked before verification) | Credentials are verified first; only failures are counted, so a valid sign-in always succeeds |
| Cancelled recording uploads kept their bytes; no storage quota | Cancel and expiry delete files; per-workspace and platform storage quotas at manifest time |
| One person with several workspaces could drain the platform's daily trials | Per-person pending and daily caps across workspaces, also counted when a Hunt is created |
| CSP was report-only and absent from sign-in pages | One enforced policy for backend and Netlify pages, with a `/csp-report` endpoint |
| Resume compared a controller digest with itself; restarts re-blocked Hunts; concurrent resumes raced | Live controller digest check, interrupted CPU trials re-run with a new request key, re-check under the lock |
| Failed physical judge could never be retried | Retry allowed after a failed job, with its own never-refunded reservation |
| Sign-out left the identity provider signed in | Sign-out ends the Privy/Dynamic session on the login page |
| "Hunt not found" right after starting a Hunt | New Hunt is shown immediately; forced refreshes are never stale |
| Other fixes | Owner-only admin changes, maintenance mode for paid agent review, orphaned-job recovery, bounded broadcast and socket caps, streaming upload hashing, reconnect/poll backoff, per-submission idempotency keys, accessibility and copy fixes |
