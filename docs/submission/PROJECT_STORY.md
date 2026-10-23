# Ghost Trials — Devpost project story

> Historical draft. The current Devpost copy, including the completed live Nemotron-reviewed CPU trial, is in [submission.md](../../submission.md).

## Inspiration

Robot policies can look reliable in a small set of demonstrations and still fail when physical conditions change. A useful evaluator should search those conditions, preserve what actually happened, and make a failure easy to repeat against the next controller. Ghost Trials is an experimental red-team platform for that job—not a safety-certification authority.

## What it does

Give Ghost Trials an executable controller, a task and a bounded trial budget. Its Hunt engine explores physical parameters, uses observed outcomes to select later experiments, repeats failures, probes a conditional failure boundary, and saves evidence-backed Ghost Cases. A saved case can be replayed with the same recipe and seed or run against a different compatible controller. “Passed this case” never means “safe in general.”

The **demonstrated, CPU-first embodiment** is a two-axis gantry arm pushing a free block into a tabletop target band. Each trial advances real MuJoCo articulation, contact, gravity and friction while a selected controller acts at every physics step. The current search controls are object mass, table/block friction, initial block position and controller delay. Those controls affect the executable model; the app rejects unsupported knobs. The built-in controllers and a bounded JSON neural-policy format run on CPU. That neural example is not a trained production policy, and none of these controllers is a Unitree G1, GR00T or SONIC checkpoint.

Each completed CPU trial retains its controller digest, seed, full recipe, simulator version, sampled telemetry, measured task result, state-derived visualization and artifact hashes. A separate verifier checks hashes, controller identity, monotonic timestamps, displacement, final position and task outcome. Hashes and trace recomputation do not prove hardware execution or real-world transfer. Generated images and landing-page illustrations are not robot-response evidence.

## How we built it

FastAPI, Pydantic and SQLite provide typed APIs, private organization-isolated workspaces, durable trial jobs, budgets, and audit records. The existing Privy sign-in remains in place. The frontend exposes Hunt, Failures, Trials, Compare and System rather than a single dashboard. A telemetry-driven replay animates **recorded simulator state samples**, explicitly labeled as not camera footage.

The Hunt uses bounded exploration followed by failure-focused repeats, mutations and one-dimensional boundary probes. It can report a boundary only when a pass/fail pair was observed with the same seed and other controls held constant. Provider errors and missing evidence are not policy failures. Synthetic development fixtures remain visibly labeled and cannot become verified Ghost Cases.

### NVIDIA and Nebius

Ghost Trials includes a task-specific reviewer for NVIDIA Nemotron Super served by **Nebius Token Factory**. When an operator enables it and budgets admit the request, each artifact-verified CPU trial makes one runtime inference call. The model receives the measured task result, selected metric values, evidence hashes and recipe—not authority to generate robot measurements. Its interpretation, cited values, model ID, latency and token usage are stored separately. Incorrect citations and disagreement with the deterministic result are flagged; provider failure leaves the measured trial intact. No local GPU is required for this remote inference.

The integration is off by default until credit-only use or provider-side spending controls are confirmed. An application-side reservation ceiling is not a guaranteed external billing limit. **Before submitting, replace this paragraph with the exact live Token Factory trial IDs and observed model results from the final deployed run. Do not claim that the new CPU reviewer ran live solely because its adapter or contract tests passed.** Earlier real Nemotron connectivity was tested on an incomplete-evidence diagnostic; that was not a robot trial.

The repository retains optional Cosmos video and G1/SONIC/Isaac worker interfaces. They have not been validated as an end-to-end G1 execution in this CPU deployment and are not represented as demonstrated features. Cosmos video, if used later, illustrates a hazard; it is not a policy-response recording.

## Challenges and learning

The hardest design boundary was separating measurement from interpretation. A generated clip or convincing model explanation can look like proof even when no robot policy ran. We made MuJoCo state and recorded telemetry the source of physical observations, with the model in an advisory role and explicit provenance on every record. We also learned to distinguish reproducibility from a broad safety claim: a repeated failure in a bounded simulator region is valuable, but does not establish behavior on every surface, policy or physical robot.

## What we accomplished and what remains

The CPU path executes real physics, discovers and reproduces failures, checks retained evidence and compares compatible controllers. The current live website runs the FastAPI CPU backend in Docker on a self-hosted VPS and the frontend on Netlify; the application itself is not hosted on Nebius AI Cloud. A submitted competition demonstration must show a genuine Token Factory runtime call from the verified-trial workflow, not merely configured credentials or a historical API probe.

Next we would validate against a more representative robot/task, gather independently reviewed failure labels, and test a compatible G1 policy on authorized compute. Until then, Ghost Trials should be judged as an evidence-conscious, autonomous **simulated-policy failure hunter**, not as a G1 safety certificate.
