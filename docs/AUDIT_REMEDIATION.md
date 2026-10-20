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

Old agent records remain readable. Records without source/runtime pinning or using oracle v1 are marked `legacy_unverified` and cannot inherit v2 validation or be replayed as source-pinned evidence. The old records are not deleted or silently upgraded.

## Demonstrated locally

- The full Python test suite passed **188 tests** after remediation. It includes actual MuJoCo execution and checked-in reference-agent subprocesses; fixtures and contract tests are not evidence of a physical G1 run.
- `uv run --frozen --extra physics --extra models --extra storage python -m scripts.multidomain_demo --output <fresh-directory>` executed both domains, verified retained evidence, replayed a physical failure with the same measured final block position, and compared distinct controllers/agent versions.
- `PLAYWRIGHT_MODULE=/root/datatruth/node_modules/playwright node scripts/check_agent_frontend.cjs` exercised the authenticated-disabled **local** mobile-sized Hunt, trace, case, and regression flow. It does not validate public sign-in or the deployed release.

## Open release gates and limitations

1. **Credential rotation — release blocker.** A Privy secret was previously exposed in conversation. The app owner must revoke/rotate it in Privy and replace the private backend environment value. Do not put the new secret in chat, Git, frontend variables, or a demo artifact. This cannot be completed by a repository patch.
2. **Hosted validation — release blocker.** Publishing source code or a review branch does not deploy or validate this remediation. Verify production auth, a fresh signed-in Hunt, replay, artifact access, quotas, health, backups, and rollback on the intended Railway/Netlify release before calling it production-ready.
3. **External-model and robotics scope.** No new paid Nebius call, live Cosmos generation, Isaac/G1/SONIC trial, arbitrary customer-agent execution, or physical robot measurement was run here. The CPU MuJoCo and bundled-agent paths are the demonstrated scope. The reference-agent subprocess is not a secure isolation boundary for untrusted customer code.
4. **Independent trust.** Hashes, source pinning, and metric recomputation detect several inconsistencies but are not hardware attestation or independent expert review.
5. **Competition media.** The owner must record and publish a genuine <=3-minute demonstration with the required key modules; existing illustrations are not execution footage.

Do not publish a production-readiness claim until the release blockers are closed and recorded with evidence.
