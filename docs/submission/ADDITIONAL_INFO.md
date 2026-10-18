# Additional info — judges and organizers

Prepared for the supplied Devpost form. Copy the answer paragraphs, not the editorial instructions. Replace every bracketed placeholder and confirm personal/legal fields yourself. Ratings must reflect your own assessment; no rating or cross-model benchmark has been invented here.

## Upload a File

Optional. Attach a small PDF or ZIP of the submission documents and non-sensitive setup notes if useful. The form's limit is 35 MB. Do not attach credentials, account databases, unlicensed checkpoints or private recordings. A file upload does not replace the required public source repository and video.

## Submitter Type

Select the actual option matching your entry: individual, team or organization. If you are submitting alone and not on behalf of an organization, choose the individual option shown by Devpost. This repository does not establish your legal status.

## Organization Name (if applicable)

If you are not representing an organization, paste:

N/A

Otherwise enter the organization's actual authorized name. Ghost Trials is the project name, not evidence of an incorporated company.

## Submitter Country of Residence

Select `[YOUR_ACTUAL_COUNTRY_OF_RESIDENCE]`. Do not infer this from your username, server location or development timezone. Check eligibility against the official rules yourself.

## Canadian province

If neither you nor any teammate resides in Canada, paste:

N/A

Otherwise provide the actual province(s) required by the form and check the applicable eligibility restrictions.

## Which track are you submitting your project into?

Physical AI Track

Editorial note: The demonstrated CPU MuJoCo gantry task executes an actual controller in physics simulation; physical hardware is not required by this track's software-only video provision. Do not describe that task as G1/SONIC execution. The separate Nebius/NVIDIA runtime requirement still needs a completed live model call in the submitted workflow.

## Is your project new or existing prior to August 26, 2026?

Select New only if the project genuinely began on or after August 26, 2026. The repository's visible initial commit is September 24, 2026, but commit dates alone cannot establish whether an earlier project existed. Confirm your actual project history.

If new, and an explanation field is available, paste only if accurate:

Ghost Trials was developed during the hackathon submission period as a new experimental robot-policy evaluation project. Its current implementation includes a CPU MuJoCo Hunt with real controller execution, bounded adaptive failure search, evidence verification, replay and regression, plus a multi-page private workspace and a separately gated Nebius Token Factory/Nemotron review integration. G1/SONIC/Isaac and live Cosmos validation remain optional, pending resources.

If existing, adapt this alternative to your actual history:

Before August 26, 2026, the project consisted of [DESCRIBE_THE_ACTUAL_PREEXISTING_WORK]. During the submission period, we added [ONLY_FEATURES_ACTUALLY_ADDED_DURING_THE_PERIOD], including the Nebius Token Factory integration for Nemotron evidence review. We also developed the evidence-provenance workflow, current evaluation guardrails and reproducibility reporting where applicable. These changes are documented in the repository history. We distinguish implemented integrations from robot-policy and Cosmos stages that have not yet been runtime-validated.

Do not submit both alternatives or invent preexisting functionality.

## Public code repository URL

https://github.com/linoxbt/ghost-trials

The repository contains an MIT license and README with development setup, architecture, provider configuration and execution limitations. Current submission materials are under `docs/submission/`. Private model credentials, organization databases and robot recordings are excluded from source control.

## Working demo URL

https://ghost-trials.netlify.app/

Editorial note: The static frontend uses a persistent Railway FastAPI CPU backend. Validate sign-in, a fresh CPU Hunt, evidence and replay on the deployed release before submitting. Historical synthetic records remain labeled; the live CPU Hunt is real simulation, not GPU/G1 or physical hardware. Nemotron review is separately gated by operator-approved spending controls.

## Which model(s) did you use, and why did you choose that size/variant?

The CPU Hunt's optional evidence reviewer uses NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) through Nebius Token Factory. It requests one bounded interpretation per artifact-verified trial and records the model suggestion separately from measured task pass/fail. We chose Super for routine review and disabled automatic Ultra escalation in this credit-limited CPU path. The older GPU judge adapter retains its two-Super-pass and Ultra-on-disagreement flow, but that path is not a demonstrated G1 run.

Earlier real API access and judge inference were exercised using an incomplete-evidence diagnostic, not a robot execution. The new CPU reviewer has contract tests against genuine MuJoCo evidence; update this answer with the exact trial ID, model ID, tokens and output only after a live Token Factory review has completed. Neither path establishes calibrated physical-safety reasoning.

Cosmos, GR00T and GEAR-SONIC are intended integration components with code and handoff instructions in the repository. Live Cosmos generation and compatible fine-tuned GR00T/SONIC execution have not yet been validated in this deployment. We do not count those stages as demonstrated model use.

## How would you rate Nemotron's output quality? What worked or fell short?

`[YOUR_OUTPUT_QUALITY_RATING]/10 — preliminary assessment`

In the limited inference verification performed so far, Nemotron produced a schema-valid, evidence-aware response to deliberately missing telemetry and classified the diagnostic as insufficient evidence. That behavior is useful for our application because a plausible narrative must not replace absent robot measurements. We prompt the model to cite specific supplied values and keep its interpretation separate from deterministic evidence guardrails.

We have not yet tested enough independently labeled robot trials to assess category accuracy, causal attribution, confidence calibration or performance across hazard types. The model's reported confidence is treated as an escalation signal, not a calibrated probability. Our application cannot infer real-world safety from this preliminary result, and this rating should not be read as a completed robotics benchmark.

Editorial note: Choose your own 1–10 rating after reviewing the actual output. If you want a rubric, rate structured-output compliance, appropriate abstention and evidence citation separately from untested robotics accuracy. Do not present untested accuracy as excellent simply because the API worked.

## Did you fine-tune, prompt-engineer, or use Nemotron out of the box?

We use hosted models without fine-tuning and apply task-specific prompt engineering. The CPU review requests structured JSON, cites exact supplied metric values, and includes an insufficient-evidence option. The application rejects invented citations and flags any disagreement with the measured outcome; model confidence remains self-reported. The separate, unvalidated G1/GPU judge path retains two-pass agreement and optional Ultra escalation.

Deterministic application guardrails independently constrain the published finding and score. Missing artifacts, unknown provenance, proxy-based measurements, legacy rubric records and uncertain judgments cannot become verified success claims. The original model assessment remains available for inspection alongside any guarded finding. This approach separates the model's interpretive role from the software's responsibility to preserve provenance and avoid unsupported conclusions.

We did not fine-tune Nemotron, and no successful fine-tuning of a task-compatible GR00T checkpoint is claimed.

## How did Nemotron compare to other models used for similar tasks?

We have not completed a controlled comparison against another model on the same independently labeled robot-trial dataset. We therefore cannot responsibly claim that Nemotron is more accurate, faster or cheaper than a competing model for physical-safety evaluation.

The observed benefit was successful integration with our structured evidence-review workflow and appropriate abstention on an incomplete-evidence diagnostic. The application also includes a deterministic development judge for testing, but that fixture implementation is not a comparable learned model or a performance baseline. Our planned evaluation will hold inputs and rubric constant, compare against independent reviewer labels, report disagreements and abstention rates, and measure latency and token usage alongside accuracy.

## Which Nebius platform capabilities were most valuable, and how?

Nebius Token Factory's hosted inference access was the most immediately valuable capability. We authenticated through its API, inspected the available model catalog and exercised real Nemotron inference without provisioning or operating our own judge-model GPU server. The application's judge connects to `https://api.tokenfactory.nebius.com/v1/`, with credentials kept in private backend configuration rather than frontend code or source control.

This shortened the path from typed trial schemas and prompts to an actual model response. It also allowed us to test an important failure case—missing robot evidence—before we had access to the much heavier robotics execution stack. Super/Ultra tier configuration is explicit, and live application admission is gated by owner-enabled execution, platform/organization budgets and confirmation of provider-side spending controls. Application reservations are admission controls, not a guaranteed provider billing cap.

We did not rent an AI Cloud GPU instance, deploy Serverless Jobs/Endpoints, or benchmark distributed scaling. Simulation deployment files and worker interfaces are preparation for that next stage, not evidence of a deployed Nebius GPU workload. Our web preview is not itself hosted on Nebius AI Cloud; the verified Nebius integration is the runtime inference API.

## How likely are you to recommend Nemotron on Nebius?

`[YOUR_RECOMMENDATION_RATING]/10`

For developers who want to prototype structured model-assisted workflows without self-hosting a large inference stack, our limited Token Factory experience was useful: real model access could be exercised independently of the unavailable robotics GPU environment. That made it possible to validate API integration and evidence-handling behavior early.

A recommendation for production physical-AI evaluation would require additional work on representative trial data, model-version reproducibility, operational reliability, latency/cost measurement and calibrated human review. We would recommend the platform for experimentation based on the access verified so far, while being explicit that we have not established production suitability or robot-safety accuracy.

Editorial note: The numeric rating is your own opinion, not an automatically measured result. Confirm it before pasting.

## Rate the inference experience compared with previous cloud/local environments

`[YOUR_INFERENCE_EXPERIENCE_RATING]/10 — limited integration experience`

Token Factory gave us a practical route to real hosted Nemotron inference while local development focused on the API, frontend and evidence contracts. We did not need to host the judge model locally to verify authentication, structured response handling and the missing-evidence path.

We have not run a same-model, same-input performance comparison against a local deployment or another cloud provider, so we cannot attach a measured speedup, availability advantage or cost reduction to this experience. The robotics environment also remains a separate infrastructure problem: hosted model inference access does not provision Isaac-compatible compute or a compatible robot checkpoint. This feedback is about the integration workflow, not a comparative infrastructure benchmark.

## What additional features or improvements would help?

The most useful improvements for this application would be clearer tooling around reproducible inference and bounded spending. We would value model-version pinning or an immutable served-version identifier in responses, detailed request-level token/latency metadata, a simple per-project hard-spend ceiling, and transparent guidance on which credits apply to Token Factory versus AI Cloud compute. These are requested capabilities, not claims that we audited their absence across the platform.

For robotics builders, an officially maintained compatibility recipe covering supported GPU types, simulator/runtime versions, GR00T embodiment configuration, checkpoint access and secure worker deployment would reduce integration uncertainty. A documented path from asynchronous trial submission to retained artifacts and model review would also help teams keep generated scenario imagery distinct from measured policy execution.

## What do you most hope to see from the Nemotron team next?

We would like stronger evidence-grounded evaluation support: reliable abstention when inputs are incomplete, confidence calibration evaluated against independent labels, and structured outputs that distinguish an observation from an inferred cause. For physical-AI review, synchronized trace/video reasoning would be particularly valuable if accompanied by transparent documentation about supported inputs and limitations.

An open evaluation set covering collisions, near misses, task completion, measurement proxies and ambiguous incident causes would help builders measure accuracy rather than rely on persuasive explanations. We would also welcome model-family guidance for choosing a fast routine reviewer versus a deeper escalation model, including empirical quality/latency/cost trade-offs on reproducible workloads.

## Did you use Tavily in your project?

No.

Ghost Trials does not currently make a functional runtime call to the Tavily API. Receiving or applying for Tavily credits does not constitute integration or qualify the project for an award requiring runtime usage.

## Builders & Brews — IRL Events City

Select only the city associated with an event you actually attended under the wording shown in this form. If you did not attend, leave it blank or choose the relevant non-participation option if available. Do not infer attendance from location or credit applications. If the form and published award rules differ, ask the organizers to clarify rather than claim attendance you did not have.

## Age-of-majority attestation

Check this only after you and every relevant teammate confirm that you meet the age-of-majority requirement where you reside. The assistant cannot verify or attest to this for you.

## Employment/conflict-of-interest attestation

Check this only after you and every relevant teammate confirm that the statement is true and review the official eligibility rules. Do not treat repository ownership, an API key or a draft submission as evidence of legal eligibility.

## Final owner review

The technical text is drafted from verified implementation status, but personal fields, ratings, project history, participation and legal attestations need your confirmation. The public demo video remains missing; confirm a live Nemotron interpretation of a verified CPU trial before claiming that runtime integration in the final entry. This document does not turn pending items into completed submission requirements.
