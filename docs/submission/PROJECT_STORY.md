## Inspiration

A robot can succeed at its normal task and still respond poorly when something unexpected happens. An obstructed aisle, a falling object, or reduced traction introduces a different question from “Can this policy complete the task?”: “What did it observe, how did it respond, and what evidence supports our conclusion?”

Ghost Trials began with that distinction. We wanted to make robot-policy evaluation more inspectable by bringing scenario definitions, response recordings, telemetry, measurement methods and model-assisted findings into one coherent workspace.

Our guiding idea is a flight recorder for physical AI: preserve the evidence behind a trial rather than reduce it to an impressive-looking score. This is an experimental evaluation platform, not an established certification authority or a claim that a robot is safe to deploy.

## What it does

Ghost Trials provides a structured workflow for defining hazards, organizing trial records, inspecting evidence and reviewing model interpretations. Its dashboard includes an overview, trial library, scenario templates, comparisons, benchmark coverage, reports, physical-recording plans, team administration and system configuration.

Each record is labeled according to its evidence source. Synthetic development records are explicitly identified as fixtures, not measurements from an executed robot. Records without validated provenance remain unverified. Operator-declared physical uploads are labeled unattested rather than silently treated as proof of hardware execution.

The experimental evaluation score is deliberately conservative. Synthetic, unverified, legacy, proxy-based, incomplete or uncertain records do not contribute to it. Records also require a live Nemotron review to become score-eligible. When eligible evidence is absent, the interface shows an unavailable score rather than inventing a reassuring number. Incompatible evaluation cohorts are not pooled into a single performance claim.

Reproducibility reports keep the policy checkpoint identity, runtime, scenario seed and recipe, response-video and raw-telemetry references, artifact hashes, validation results and measurement limitations together. This lets a reviewer inspect the basis for a finding without confusing an AI explanation with a measurement.

## How we built it

The backend uses Python, FastAPI, Pydantic and SQLite. It exposes typed trial APIs and streams progress over WebSockets. A persistent job queue retains job states across restarts, while private artifact routes enforce organization-level ownership. Individual identity and team access use Privy-backed authentication, organization membership, role checks, session revocation and an audit trail.

The frontend combines a responsive JavaScript application with a React-based authentication integration, a custom orange visual identity, collapsible navigation, mobile layouts and dedicated pages for the major evaluation workflows. The landing-page humanoid visualization is explicitly an illustration, not evidence that a simulator ran.

The execution architecture separates three responsibilities:

1. Scenario generation produces a structured hazard definition and, when an authorized Cosmos service is available, an illustrative world-model video.
2. Policy execution runs a supported robot stack on an authorized worker and returns telemetry, a response recording and the executed configuration.
3. Evidence review interprets captured measurements, while deterministic evidence guardrails control which conclusions and scores the application can publish.

This separation matters because a generated scenario video cannot establish what a robot actually did. Only a recorded policy execution or an authorized physical recording can supply that evidence.

## NVIDIA models and Nebius

The implemented judge uses NVIDIA Nemotron through Nebius Token Factory's inference API. It requests structured, evidence-citing findings from two Nemotron Super passes and escalates to Nemotron Ultra when categories disagree or reported confidence is low. A larger model is used for unresolved cases, not automatically for every request.

Real Token Factory authentication and Nemotron inference have been verified with a deliberately incomplete evidence probe. The probe returned an insufficient-evidence finding. That confirms access to a real hosted NVIDIA model, but it is not a completed robot trial or a validation of judge accuracy on physical events.

Token Factory allowed us to exercise the model-review integration without first procuring a GPU machine or self-hosting the judge. We did not provision Nebius AI Cloud GPU compute, and we do not claim Serverless Jobs, Serverless Endpoints or a specific GPU instance type as deployed components.

Production integration code is included for Cosmos video generation and remote robot-policy execution. The intended G1 workflow uses a compatible fine-tuned GR00T policy with GEAR-SONIC whole-body control. Compatible weights, authorized compute and runtime validation remain necessary. We do not present that intended workflow as already demonstrated.

## Evidence validation and reproducibility

For remote simulation evidence, the application retains worker artifacts, checks content hashes, separately recomputes metrics from telemetry and decodes the response video before treating the bundle as artifact-validated. These checks are implemented separately from the worker's metric reducer. They detect several forms of incomplete or inconsistent evidence, but cannot prove that a self-consistent bundle was produced by trustworthy hardware.

For physical capture, an implemented read-only Unitree observer is designed to record joint feedback, IMU orientation, externally issued motor commands and camera footage. The upload workflow checks identity declarations, file integrity, timestamps, freshness, video decoding and measurement consistency. It never commands robot motion. This recorder has been tested with synthetic fixtures, not a physical G1.

We also distinguish measurements from proxies. A change in motor commands after an operator marker is not proof that the policy recognized a hazard. Minimum clearance cannot be inferred reliably from joint positions alone; it requires suitable calibrated external measurements. Recorded outcomes, metric basis and uncertainty remain visible to the reviewer.

## Challenges we faced

The central challenge was not building another dashboard. It was making the evidence contract honest across development data, external services and eventual robot execution.

During development, seeded fixtures made interface and API testing repeatable. However, a convincing fixture can be mistaken for a real policy measurement if its provenance is not visible. We addressed that by labeling demo records prominently, excluding them from scores, preserving original findings for inspection and failing closed when real execution is unavailable.

Compute and checkpoint access also constrain validation. A Token Factory key provides hosted inference access; it does not supply a robot, an Isaac-compatible GPU worker or a task-compatible fine-tuned policy. We built configuration checks and blocked execution states so missing resources do not become fabricated results.

Another challenge was separating integrity checking from independent validation. Hashes and metric recomputation are useful engineering controls, but they are not external certification, human review or GPU attestation. Ghost Trials reports those limits directly.

## What we learned

We learned that provenance is a product feature, not a small metadata detail. A reviewer needs to know whether a value came from a fixture, a simulator, an operator observation or a calibrated sensor before deciding what it means.

We also learned that missing evidence should change the interface and the conclusion. An unavailable score, an explicit execution blocker and a retained partial artifact can be more informative than a confident narrative.

Finally, repeatability depends on more than a random seed. Policy weights, executed recipes, software versions, hardware and measurement definitions all affect a trial. A defensible report must preserve those identities and state what remains uncertain.

## Accomplishments

We built a coherent multi-page evaluation workspace with private team access, persistent jobs, evidence inspection, comparison controls, provenance-aware scoring and structured exports. We implemented a physical-recording handoff that lets a team prepare capture plans before it obtains hardware access.

At the September 28, 2026 verification snapshot, 124 automated tests passed. Browser checks covered evidence labels, unavailable scores, provenance filters, reproducibility downloads and layouts at phone and desktop widths. These tests establish software behavior on fixtures, not successful robot execution.

## Current status and what's next

The current deployment has no demonstrated end-to-end GR00T/GEAR-SONIC policy trial, no validated live Cosmos generation and no physical robot measurement. Existing trial records are demo evidence and are excluded from the experimental score. Real model connectivity is verified; physical safety performance is not.

Our next milestone is one actual recorded policy trial with compatible weights and authorized compute, retained telemetry and response video, a live Nemotron review, and a robotics reviewer inspecting provenance, timing and measurement limitations. We will then assess reproducibility across a small scenario set and compare model findings against independently supplied labels.

Ghost Trials' contribution is the evidence workflow: a place where scenarios, measurements, interpretations and limitations can be reviewed together. Our ambition is to make robot evaluation more accountable, without claiming that an unvalidated score replaces expert judgment or a formal safety process.
