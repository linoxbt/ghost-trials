# A credible Ghost Trials demonstration

Ghost Trials is an experimental evaluation platform, not a safety-certification service.
No genuine robot-policy execution has yet been demonstrated in this deployment.
Do not use synthetic or unknown-provenance records as evidence of real robot behavior.

## One recorded policy trial

1. Obtain authorized compute and a compatible fine-tuned checkpoint, or partner with an on-site G1 team operating an approved policy. An API key does not provide a robot or GPU compute.
2. Configure the live worker, exact checkpoint digest, and provider credentials privately. Confirm provider spending controls and platform/organization admission budgets before enabling live execution. See LIVE_EXECUTION.md and GPU_ACCEPTANCE.md. Recording physical operation instead requires PHYSICAL_ROBOT.md and an on-site operator; the recorder never actuates the robot.
3. Run one supported low-risk scenario through the actual policy. For a simulation-first demonstration, create the trial through the app only after configuring the worker. It captures video, telemetry, executed recipe and hashes, validates retained artifacts, and requests Nemotron review. Never substitute a fixture on failure. GPU acceptance is a separate worker diagnostic and does not itself invoke Cosmos or the judge.
4. Inspect the response video and trace. Check hazard onset, camera timing, checkpoint configuration, units, and whether each measurement is a proxy. Have a robotics reviewer document their own observations. Automated recomputation is not independent human review or hardware attestation.
5. Export the reproducibility report and download its authorized artifacts. Include the saved checkpoint digest, scenario recipe/seed, actual runtime version, original model assessment, validation results and limitations. Identical seeds do not guarantee identical GPU results.

The dashboard's real-trial milestone requires a completed simulation record with retained artifact checks, decoded video and a Nemotron review. It does not prove trustworthy physical execution, independent reviewer identity, safety, or hackathon compliance. Physical recordings are deliberately labeled operator-declared and unattested. Proxy measurements can demonstrate recorded operation, but remain excluded from weighted scores.

## Separate evidence from presentation

- Synthetic demo: generated numeric fixtures; no robot executed the trial.
- Unverified: provenance/artifact validation is absent; never claim a real run.
- Physical, unattested: uploaded operator-declared recording; not hardware attestation.
- Artifact-validated simulation: retained hashes and separately recomputed metrics passed; video decoded. Not proof of simulator fidelity or external certification.
- Score-eligible: additional current-rubric, non-proxy, complete-artifact and live-review checks passed. This still produces only an experimental cohort metric.

Legacy findings are preserved, not silently rewritten or deleted. All-evidence charts display stored findings, including demo data; the evaluation score uses only eligible records within one compatible cohort. Missing scores are null/“—”.

## Honest demo language

Say: “We recorded this policy in this environment, retained its telemetry, and used Nemotron on Nebius to review the evidence.” Show actual modules and identify the backend correctly (SONIC/MuJoCo is not Isaac Sim).

Do not say: “This robot is certified safe,” “Cosmos measured the robot,” “unit tests prove the GPU integration,” or “this score is a real-world failure probability.” Missing integrations must be marked pending, not described as demonstrated.
