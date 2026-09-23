# Evaluation methodology and submission readiness

## Product scope

Ghost Trials helps a robotics evaluation engineer inspect policy failures in simulation. It is not a certification authority. Generated Cosmos footage illustrates a scenario; simulator measurements describe the executed physical trial. Do not imply that pixels are converted into exact simulator state or prove physical correctness.

## Workspace

- `/app/#/compare`: pick baseline and candidate records, inspect compatibility warnings and metric deltas, link playback positions, export the comparison. Viewing this page never launches compute.
- `/app/#/benchmarks`: inspect hazard/severity coverage, unique seeds, recorded falls/collisions, completed tasks, insufficient evidence, and execution errors. Cohorts remain separate by checkpoint, embodiment, simulator, rubric, and evidence origin.
- Trial detail: the evidence inspector separates fixed threshold checks from model interpretations. Timestamp buttons seek the policy recording, not the Cosmos video. Missing timestamps stay missing. Worker-reported hashes are not independent attestation.

Read-only API: `GET /comparisons?baseline=ID&candidate=ID`, `GET /benchmarks`, `GET /trials/ID/evidence`.

`POST /trials/ID/replay` reuses a completed trial's saved scenario and recipe without calling the scenario generator again. It executes the currently configured simulator and judge, records `replay_of`, and can incur provider charges in production. Set `GHOST_POLICY_NAME` when changing the served policy; the checkpoint digest remains the identity used for comparisons. A replay does not promise bitwise determinism. Never compare only the prompt and assume the generated scenarios match.

## Rubric warehouse-evaluation-v3

| Severity | Reaction target | Clearance target |
| --- | --- | --- |
| Low | 700 ms | 0.35 m |
| Medium | 500 ms | 0.50 m |
| High | 350 ms | 0.65 m |

These are engineering demonstration thresholds, not validated industry limits. They override generated prose so a model cannot silently redefine the scoring criteria.

Reduced traction uses a 500 ms response target and maximum measured contact slip of 0.2 m/s instead of clearance. Effective ground friction must be recorded. The SONIC/MuJoCo recipe changes the entire static ground plane at 3 seconds: low severity μ=0.4, medium μ=0.2, high μ=0.05. This is not a localized spill or fluid simulation. Contact-physics tests run on CPU; the G1 policy still needs GPU validation. The Arena backend rejects this recipe before launching a job.

Avoided requires the thresholds, no recorded fall/collision, and task completion. Mitigated describes a partial observed response, not proof of causal risk reduction. A recorded fall/collision is a failure, not sufficient evidence for catastrophic causation. Proxy-only measurements, incomplete real-run evidence, or low judge confidence cannot support a pass. Insufficient-evidence outcomes are excluded from the weighted score and counted visibly. A null reaction latency is not zero. The model's confidence is not calibrated.

Current runners use response proxies; this deliberately prevents claiming established avoidance from their response measurements alone. A controlled response measure and human validation are still needed. Original model output is retained before guardrails; legacy records are not rewritten.

## Fair comparisons

Compare identical scenario content, recipe, seed, severity, embodiment, simulator, and rubric. Record both checkpoint digests. Equal checkpoints produce a repeatability comparison; different checkpoints produce a policy comparison. Missing provenance and synthetic records cannot establish a policy improvement. Even matching metadata does not prove deterministic GPU execution or real-world generalization. Report results across multiple paired seeds, including failures and task completion; never select only successful examples.

## Bounded experiments and review audit

Plan a search without calling any provider:

```bash
.venv/bin/python -m ghost_trials.experiments --strategy adaptive --hazard falling_object --max-trials 6
```

Add `--execute` to run the currently configured pipeline. Non-local providers also require `--confirm-paid-execution`; **max-trials is not a monetary spending limit**. Reports and isolated state are written to a new `data/experiments/experiment_ID/` directory, without changing the dashboard's records. The CLI does not rent or shut down GPU hosts. `--strategy random` provides an equal-trial-budget baseline; `--strategy grid` traverses the discrete severity/seed grid. Use the same seeds, policy and budget when comparing strategies. Run both supported hazard families separately.

Adaptive search moves toward lower severity after an observed failure and higher severity otherwise. It reports the lowest *observed* failure, never an absolute minimum. Failures mean recorded falls/collisions or incomplete tasks; provider errors stop the search and are not robot failures. The method does not assume monotonic failure rates, nor does it invent physical parameters from video. CPU tests validate orchestration on synthetic fixtures only.

For human review, export the evaluation from Reports and obtain independent labels in a JSON array with `trial_id`, `score_category`, `reviewer`, and `rationale` fields. Do not auto-generate reference labels with the same judge. Run:

```bash
.venv/bin/python -m ghost_trials.review_audit evaluation.json reviews.json
```

This produces an agreement rate, confusion matrix, Cohen's kappa where defined, and disagreements. Missing labels produce no agreement claim. Reviewer independence and the quality of reference labels require an actual review process; the tool cannot authenticate them.

## Remaining work requiring actual execution

- Validate one compatible G1 backend end to end with a real checkpoint, GPU, and provider account.
- Run a controlled baseline/candidate comparison and retain original recordings and traces.
- Implemented recipes: falling object and path obstruction on both backends; reduced traction on SONIC/MuJoCo only. All require GPU policy acceptance before claiming G1 execution.
- Gather a human-reviewed sample and report label agreement and disagreements. No human-validation result is claimed by this repository.
- The implemented bounded adaptive failure search must be GPU-validated against random search under the same trial budget before claims about search efficiency.
- Obtain feedback from a robotics evaluation engineer on the report and the release decision it supports.

## Under-three-minute demo

1. 0:00–0:20: a genuine recorded failure, labeled with policy and scenario.
2. 0:20–0:40: identify the engineer's problem and show the execution configuration.
3. 0:40–1:45: show real key modules executing; inspect video and telemetry.
4. 1:45–2:25: compare a matched pair and inspect benchmark limitations.
5. 2:25–2:50: export the evidence report, explain Nebius/NVIDIA usage and remaining limits.

Keep a clearly labeled previously recorded run available for outages. Do not portray replay as live generation. Publish the repository with its license, setup instructions, tools feedback, and any pre-hackathon changes disclosed. Confirm the official rules before submission.
