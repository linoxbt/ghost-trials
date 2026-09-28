# Submission evidence status

Snapshot: September 28, 2026. Refresh after any actual model, simulation or hardware run. This is a development-status record, not independent attestation.

## Verified within the current scope

- The Python application test suite passed: **124 tests**. These include deliberately synthetic fixtures, mocked provider contracts, organization isolation, physical-upload validation and score-exclusion behavior.
- Browser checks passed at 320, 390 and 1440 pixel widths for provenance labels/filters, unavailable scores, pending real execution, reproducibility downloads and layout.
- Real Nebius Token Factory authentication and Nemotron inference have been exercised. An incomplete-evidence diagnostic returned `insufficient_evidence`; it was not a robot trial and did not establish physical-safety accuracy.
- The September 23 local connectivity record captured a Super diagnostic using 714 total tokens. A subsequent bounded two-pass/escalation probe verified the configured integration path. No cost, latency or accuracy benchmark is inferred from these checks. Private validation files are not committed to the repository.
- The application retains trial evidence and offers server-side integrity checks, separately recomputed metrics and video decoding. Successful fixture checks demonstrate implementation behavior, not actual G1 execution.
- CPU MuJoCo contact-physics tests cover the reduced-traction implementation. That is not a GR00T/SONIC policy trial or Isaac Lab-Arena validation.

## Current stored records

The inspected development database contained **23 completed legacy/demo records**. Nine explicitly declared synthetic metrics; the remaining fourteen originally had unknown metric origin, but their deterministic development-judge identifiers identify them as legacy synthetic records. The current evidence classifier labels all 23 synthetic demo records and excludes them from the experimental score.

At this snapshot:

- Score-eligible records: **0**.
- Experimental score: **unavailable / null**, not zero.
- Physical recording sessions stored: **0**.
- Genuine end-to-end policy-execution milestone: **pending**.

These are local deployment counts, not a benchmark dataset. They may change with use and should not be presented as measured robot performance. Original stored findings are preserved for inspection rather than rewritten as real evidence.

## Implemented but not demonstrated end to end

- Authorized Cosmos video-generation client paths and artifact retention.
- Authenticated remote worker interfaces for policy execution and returned telemetry.
- Compatible checkpoint access/identity checks and deployment handoff tools.
- G1 read-only joint/IMU/command and camera recording workflow.
- Nemotron review of an actual robot-policy trial or actual physical capture.
- External robotics-review and repeatability workflows.

## Still required

- An authorized GPU worker and compatible fine-tuned policy checkpoint, or a robotics partner with an approved externally running G1 policy.
- Live Cosmos access if generated world-model video is included in the demonstrated pipeline.
- One recorded policy execution, raw telemetry, executed configuration and reproducibility export.
- Live model review of that actual trial, plus human inspection of provenance, timing and measurement quality.
- A public demo video and final owner-completed Devpost fields.

No physical hardware operation, GPU execution, independent reviewer assessment, production scale, safety certification, calibrated failure probability or comparative model benchmark is claimed.

## Reproduce software checks

Run the test suite in development mode with the documented optional dependencies:

```bash
uv sync --extra dev --extra physics --extra models --extra storage
uv run pytest -q
```

FFmpeg/ffprobe must be available for recording-validation tests. Browser scripts require a locally installed Playwright/Chromium setup; the evidence frontend check targets an isolated fixture server on port 8013, not a customer's live deployment. Never use the browser fixture script to create fake evidence in a real organization workspace.

The application offers `GET /demonstration-readiness` and `GET /trials/ID/reproducibility` behind its normal private-workspace authorization. These endpoints are read-only and do not launch GPU or paid inference jobs. A readiness result is a narrow evidence milestone, not hackathon approval or hardware attestation.
