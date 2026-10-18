# Submission evidence status

Snapshot: October 16, 2026. This is an engineering validation record, not independent robotics attestation or safety certification. Refresh it after the deployed release is tested.

## Demonstrated CPU execution

- `python -m scripts.cpu_smoke --trials 16 --strategy adaptive` ran a real headless MuJoCo tabletop Hunt with an executable gantry-arm controller. It completed **16 physics trials** and found **three failures** in the bounded tested space.
- A retained Ghost Case passed `cpu_trace_metrics_verified` artifact and metric verification. Exact replay reproduced the measured final block position: **0.625826 m** in both baseline and replay.
- The `gantry-push-v2` controller was actually executed against that saved recipe and measured **0.776821 m**, passing this specific case (`fixed_on_case`). This does not establish that the candidate controller is generally safe.
- The automatic reproduction status was `reproducible`. An empirical object-mass transition was recorded only for the tested pair and versions, not as a universal threshold.
- The CPU backend retains simulator version, controller checkpoint digest, recipe, seed, measured telemetry, trajectory, evidence manifest, and replay information. Its trajectory graphic is state-derived; it is not camera or robot video.

The smoke command deliberately disables all external model calls. Its artifacts were generated locally under `/tmp/ghost-competition-20261016/` and are not a published, independently reviewed dataset. The smoke verifies a local application workflow, not the deployed website or physical hardware.

## Model and provider status

- A prior bounded Nebius Token Factory diagnostic exercised real Nemotron inference on incomplete evidence. It was **not** an evaluated robot trial.
- The new optional CPU Nemotron reviewer is integrated with verified MuJoCo evidence, transactionally reserved application budget, exact metric-citation checks, and a distinct interpretation record. Its automated provider-boundary tests use `httpx.MockTransport`; **a live model review of a completed CPU trial has not yet been demonstrated**.
- Live CPU review remains disabled by default. Before enabling it, confirm the provider's credit-only or hard-spend controls, allocate the organization budget, confirm the current model ID, and run one bounded trial. Application-side admission limits do not guarantee an external billing ceiling.
- No Nebius AI Cloud GPU, Isaac/G1/SONIC execution, physical G1 run, live Cosmos generation, or robotics-expert independent review is claimed.

## Deployment and submission checks still required

- Validate sign-in and a fresh CPU Hunt, evidence report, replay, and comparison on the deployed Netlify/Railway release.
- If the team wants to claim runtime NVIDIA-model use in the demonstrated CPU flow, complete one authorized live Nemotron review and retain its response and usage alongside measured trial evidence. Do not call contract tests a live inference demonstration.
- Have a robotics reviewer inspect the configuration, controller identity, trace, measurement definitions, and repeatability limitations.
- Record and publish the three-minute-or-shorter demo showing at least one minute of actual key modules operating. Complete owner-specific Devpost fields and confirm hackathon eligibility.

## Reproduce the local software checks

```bash
uv sync --extra dev --extra physics --extra models --extra storage
uv run pytest -q
uv run python -m scripts.cpu_smoke --trials 16 --strategy adaptive
```

The application exposes private `GET /demonstration-readiness` and `GET /trials/{id}/reproducibility` endpoints. They are evidence aids, not approval or attestation.
