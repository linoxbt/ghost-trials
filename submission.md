# Ghost Trials — Devpost submission dossier

**Nebius x NVIDIA Global AI Hackathon · Physical AI Track**
**Prepared 18 October 2026 · Submission draft, not a safety certificate**

> **Owner review before submission:** add a public YouTube video URL; confirm your country, project start date, eligibility, event attendance, and personal 1–10 ratings. Record a fresh signed-in Hunt on the hosted site. Do not paste the editorial notes or bracketed placeholders into Devpost.

## Project overview — paste into Devpost

**Project name:** Ghost Trials

**Elevator pitch:** Give Ghost Trials a robot controller and a task. It searches bounded physical conditions for failures, verifies and reproduces the evidence, then tests whether the next controller fixes the case.

**Track:** Physical AI Track

**Repository:** https://github.com/linoxbt/ghost-trials

**Working application:** https://ghost-trials.netlify.app/

**Demo video:** `[PUBLIC_YOUTUBE_URL — REQUIRED BEFORE SUBMISSION]`

**Built with** (select up to 25 tags): Python, FastAPI, Pydantic, MuJoCo, SQLite, JavaScript, React, Privy, WebSockets, NVIDIA Nemotron, Nebius Token Factory, HTTPX, Docker, Pytest, Railway, Netlify, GitHub.

The GitHub repository includes the MIT license, setup instructions and source code. The hosted frontend is on Netlify; its FastAPI CPU backend is on Railway. The required NVIDIA-model runtime integration is **Nemotron 3 Super through Nebius Token Factory**, not Railway hosting. We have not used Nebius AI Cloud GPU compute or claimed Serverless Jobs/Endpoints as deployed infrastructure.

## Project story — paste into “About the project”

### Inspiration

A robot controller may succeed under nominal conditions and fail when friction, object placement, mass or timing shifts. The useful question is not simply “What score did it get?” It is: **Which physical condition caused a repeatable failure, what did the robot actually do, and can a reviewer inspect and rerun the evidence?**

Ghost Trials grew from that question. We wanted an experimental red-team workflow for embodied AI: give it an executable policy, define a task, and let it search *bounded, simulator-supported* conditions for weaknesses. The product is not a certification authority, and a passed set of trials is not evidence that a robot is safe to deploy.

### What it does

The primary workflow is **Connect controller → Define task → Release the Ghost → Inspect trials → Reproduce failure → Save Ghost Case → Compare another controller → Hunt again**.

The demonstrated default task runs entirely on CPU. A two-axis gantry arm pushes a free block across a tabletop toward a target band. MuJoCo advances articulated motion, gravity, contact and friction; the selected executable controller issues actions on each physics step. The Hunt can vary object mass, surface friction, initial block position and controller delay—parameters that affect the implemented model. Unsupported controls are rejected rather than displayed as decorative settings.

The Hunt samples the declared search space, then uses observed failures and near-failures to focus later candidates. It mutates nearby physical conditions, repeats potential failures and, when a matched pass/fail pair exists, reports an **empirical boundary within the tested region**. It does not claim to find a global worst case or universal safety threshold. A verified finding becomes a Ghost Case: a reusable recipe, seed, controller digest, simulator version, telemetry and artifact manifest. Exact replay and compatible-controller regression answer the narrow question “Did this candidate pass this case?”—not “Is the candidate generally safe?”

The workspace presents Hunt, Failures, Trials, Compare and System views. It shows trial progress, measured task outcome, a telemetry-derived state replay, search observations, evidence checks, model interpretation and known limitations. The replay is generated from recorded simulator states; it is **not camera footage or a Cosmos-generated robot response**. Authenticated users have organization-isolated records. New workspaces do not automatically receive paid-inference access.

### How we built it

The backend uses FastAPI, Pydantic and SQLite with a durable job queue, typed trial records, private artifact routes, role checks, budget admission and audit records. The frontend is a responsive multi-page application with Privy-backed sign-in. CPU simulation is a distinct adapter within the existing `ScenarioGenerator → Simulator → TrialJudge → evidence` pipeline; optional Cosmos, Isaac and SONIC/G1 integrations remain modular and fail closed when their resources are absent. Synthetic fixtures are development-only and cannot silently replace real execution.

Evidence is not a single LLM answer. For each completed CPU trial, the system retains the full physical recipe, random seed, controller identity/digest, simulator version, sampled state trajectory, measured metrics, task outcome, state-derived visualization and hashes. A separate verifier checks artifact integrity and recomputes selected results from the trace. Missing or corrupt evidence is not converted into a policy verdict. Provider outages are recorded as provider failures, not robot-policy failures. Observation and AI interpretation remain separate in the UI and API.

### NVIDIA models and Nebius

Ghost Trials uses **NVIDIA Nemotron 3 Super** (`nvidia/nemotron-3-super-120b-a12b`) through **Nebius Token Factory's runtime inference API** to interpret an artifact-verified CPU trial. The reviewer receives the measured task outcome, selected numeric metrics, recipe, simulator/checkpoint identities and evidence manifest. It must return structured JSON and cite exact supplied metric values. Invalid or invented citations are rejected; disagreement is flagged; a model failure cannot overwrite the deterministic MuJoCo result.

On 18 October 2026, an operator acceptance trial completed real MuJoCo simulation and a live Token Factory call. Trial `trl_9dad0149b31e` ran `gantry-push-v1` for **3.0 simulated seconds** with seed 42 and placed the block at **0.729056 m**, inside the **0.64–0.86 m** target band. The evidence checker reported `cpu_trace_metrics_verified` after checking **121 telemetry samples and four core artifacts**. Nemotron Super returned a completed **pass** interpretation, with **801 prompt tokens and 375 completion tokens**. This is one observed integration result, not a model-accuracy benchmark or independent safety review. An earlier attempt returned an invalid model response; the app retained the physical measurement and now records a safe error reason. The successful operator report was generated locally; the repository's public seed-42 reference bundle contains separately generated physics evidence **without** a model review. A fresh signed-in customer trial on the deployed site remains a separate validation step.

Token Factory removed the need to procure a GPU merely to host the judge. The robot physics still executes locally or on ordinary CPU infrastructure; remote model inference is not robot execution. The CPU reviewer makes at most one Super request per admitted verified trial and has no automatic Ultra fallback. The older optional GPU judge path contains two-pass Super/Ultra escalation, but that path has **not** been demonstrated with a G1 checkpoint. Application budget reservations are admission controls, not a guarantee about an external bill. The owner confirmed Nebius automatic top-up is off before the live acceptance call.

### Challenges, learning and impact

The hardest boundary was resisting plausible but unsupported claims. A polished synthetic clip, a model's confident prose or an artifact hash can each look persuasive without proving that a policy ran. We made measured simulator state the source of physical observations, labeled synthetic and unauthenticated data, and displayed unavailable conclusions when evidence is insufficient. Hashes and metric recomputation detect several inconsistencies but do not prove trusted hardware execution, prevent every self-consistent forgery or establish transfer to a physical robot.

We also learned that reproducibility is more than a random seed. Controller digest, simulator version, recipe, timing, metric definitions and evidence provenance all matter. A useful failure report should make those identities visible so a robotics engineer can reproduce and challenge the finding.

The potential users are robotics teams and policy developers who need to prioritize regressions before deploying a new checkpoint. The immediate value is a repeatable, evidence-backed adversarial test of an **executable controller in a defined simulator task**. It is not a regulator-approved certification result, a general robot-safety probability or a replacement for physical validation and expert review.

### What we accomplished and what remains

A bounded local adaptive CPU Hunt completed **16 real MuJoCo trials and found three failures**. A saved case replayed with the same measured final block position (**0.625826 m**); a different compatible controller executed the same recipe and reached **0.776821 m**, passing that *particular* case. A guided six-trial Hunt also found one reproducible case in a local API test. These are simulator results from the documented development validation, not physical G1 trials. The codebase's full automated suite passed **171 tests** at the 18 October snapshot; tests include actual MuJoCo execution as well as synthetic algorithm fixtures. Tests alone do not establish independent robotics validation.

The hosted backend is running CPU/MuJoCo on Railway and the Netlify health proxy responds. Live Nemotron review is configured on that backend, but paid review still requires an operator-assigned budget for a particular signed-in organization; no public new account receives it automatically. The final video should show at least one minute of the actual Hunt, policy execution and evidence views, and should show a completed model review only if that signed-in trial really received one.

The original Unitree G1/GR00T/GEAR-SONIC/Isaac concept remains an optional, unvalidated integration path. No physical G1, compatible fine-tuned G1 checkpoint, end-to-end G1 worker run, live Cosmos generation or Nebius AI Cloud GPU instance is claimed. The next engineering milestones are a signed-in production Hunt with a budgeted review, an independent robotics assessment of trace and measurement limitations, and a compatible G1 run if hardware/compute access becomes available.

## Additional-info answers — paste field by field

### Submitter type, organization and residence

- **Submitter Type:** Individual (as selected in the supplied form; verify before final submission).
- **Organization Name:** `N/A` if you are not representing an organization.
- **Country of residence:** `[YOUR ACTUAL COUNTRY — SELECT IN DEVPOST]`.
- **Canadian province:** `N/A` only if neither you nor a teammate resides in Canada; otherwise provide the actual province and check eligibility.
- **Track:** Physical AI Track.
- **New or existing before 26 August 2026:** `[OWNER TO CONFIRM]`. The visible repository history does not prove when the idea or earlier private work began. If it predates the period, describe the specific Hunt, MuJoCo, evidence and Token Factory work completed during the submission period; do not mark it “new” merely from the first public commit date.

### Public code and demo URLs

**Public repository:** https://github.com/linoxbt/ghost-trials

**Working application:** https://ghost-trials.netlify.app/

**Video:** `[PUBLIC_YOUTUBE_URL]`

The repository has an MIT license, installation instructions and run commands. The hosted app requires normal Privy email sign-in for private Hunt functions. Judges do not need a special shared login; they may sign up normally. A new workspace's paid model review is disabled until an operator allocates its budget. A local CPU Hunt needs no paid service, GPU or API key.

### Which model(s) did you use, and why that size/variant?

We used NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) through Nebius Token Factory for a **single, bounded interpretation of each admitted, artifact-verified MuJoCo trial**. Super offers a capable hosted reasoning model without self-hosting a large model on our CPU server. The response is advisory and must cite supplied metrics; the app's deterministic task outcome and evidence checks remain authoritative. One live Super review of a completed measured trial succeeded in operator acceptance. The CPU path does not automatically invoke Ultra. Cosmos, GR00T and SONIC code exists as optional integration work but is not counted as demonstrated model execution here.

### How would you rate Nemotron's output quality? What worked or fell short?

**Numeric selection:** `[OWNER: CHOOSE 1–10 AFTER REVIEWING THE ACTUAL OUTPUT]`

In the observed live trial, Super returned a structured pass interpretation consistent with the measured target-band outcome and supplied metric values. It also previously returned one invalid response, which the application rejected while preserving the physical result. This small sample supports a claim that the integration can work and that its fail-closed handling matters—not a measured claim about judge accuracy, calibration or reliability across robot incidents. We still need an independently labeled set of diverse cases to evaluate those properties.

### Did you fine-tune, prompt-engineer, or use Nemotron out of the box?

We did **not** fine-tune Nemotron. We use the hosted model with a task-specific system prompt, structured JSON request and response validation. The prompt tells it to distinguish observation from interpretation, cite exact supplied metric values, and abstain when evidence is insufficient. Code validates those citations and stores model status, latency, token usage, evidence digest and interpretation separately from measured task success. One provider response failed validation; it was not silently retried or presented as a robot failure.

### How did Nemotron compare with other models for similar tasks?

We have **not** conducted a controlled, independently labeled comparison against another model on the same robotics evidence set. The deterministic task evaluator and synthetic test fixtures are not competing LLMs. We can compare integration behavior—structured citations, rejection of invalid output and bounded inference—but cannot responsibly claim superior accuracy, speed or cost. A future comparison should hold task data and rubric constant and report agreement, abstention, latency and token use against independent labels.

### Which Nebius capabilities were most valuable, and how?

Nebius Token Factory's OpenAI-compatible hosted inference endpoint was the capability we used. It served a runtime Nemotron Super request connected to a real, verified MuJoCo trial without requiring us to self-host the reviewer on a GPU. This let the CPU-first simulator and cloud model reviewer develop independently. The API key is held in private backend configuration; the browser does not receive it. Per-trial admission requires verified evidence, an enabled review flag and platform/organization budgets. We did not provision Nebius AI Cloud GPUs or deploy Nebius Serverless Jobs/Endpoints, and we do not describe Railway as Nebius infrastructure.

### How likely are you to recommend Nemotron on Nebius?

**Numeric selection:** `[OWNER: CHOOSE 1–10]`

For an experimental evidence-review workflow, Token Factory provided a direct route from measured trial JSON to a real NVIDIA model response. We would recommend evaluating it to developers who want hosted inference without managing model-serving hardware. Our recommendation remains qualified: one successful model-reviewed robotics trial and one invalid response are not enough to establish production reliability or physical-safety accuracy.

### Rate Nebius inference against previous cloud/local environments

**Numeric selection:** `[OWNER: CHOOSE 1–10 BASED ON YOUR OWN EXPERIENCE]`

It was practical to integrate and test hosted Super from a CPU-only development environment. We did not run the same Nemotron checkpoint locally or on another cloud under matched load, so we have no defensible speedup or price-performance comparison. The successful live call returned token-usage metadata; a provider response also failed validation. We treat that as a reason to keep retry, observability and evidence boundaries explicit rather than infer a general reliability ranking.

### What additional features would improve the experience?

For evidence-sensitive applications we would value immutable served-model version identifiers in responses, clearer structured-output and reasoning-mode guidance per model, request-level usage/latency diagnostics, and project-level spending controls that are easy to verify before activation. For physical-AI builders, maintained recipes connecting simulator versions, checkpoint formats and secure workers would reduce compatibility uncertainty. These are product requests, not claims that every capability is absent from Nebius.

### What would you like from the Nemotron team next?

We would welcome benchmarked evidence-grounded review: calibrated abstention on missing inputs, reliable exact-value citation, explicit separation of measurement from inferred cause, and public guidance on Super-versus-Ultra trade-offs. A reproducible robotics incident set with independent labels and synchronized trace/video inputs would help teams measure model quality instead of relying on persuasive prose.

### Tavily, event and eligibility fields

- **Tavily runtime use:** No. No functional Tavily API call is part of the current app.
- **Builders & Brews city:** Select only an event city you actually attended; otherwise leave blank or choose the form's nonparticipation option.
- **Age-of-majority and conflict-of-interest checkboxes:** Only you can confirm and check these after reviewing the official rules.
- **AI tools used while building:** OpenAI Codex for coding/documentation assistance; NVIDIA Nemotron 3 Super on Nebius Token Factory as the app's runtime model. Add other tools only if you actually used them.
- **Level of learning:** `[OWNER: SELECT THE OPTION THAT MATCHES YOUR EXPERIENCE]`. Suggested explanatory text, if requested: “I learned to separate real simulator observations from model interpretation, to preserve reproducible evidence, and to design fail-closed spending and execution gates for a hosted AI service.”
- **Career AI value:** `[OWNER: SELECT YOUR HONEST ANSWER]`. Suggested explanation, if requested: “The project gave me practical experience integrating an open NVIDIA model into an evidence-sensitive robotics workflow and evaluating its limits.”

## Media captions and demonstration plan

Use only screenshots of the real app or recorded telemetry. Suggested captions (each under 140 characters):

1. **Hunt:** “Release the Ghost: a bounded search across mass, friction, initial position and controller delay.”
2. **Trials:** “Each trial shows measured MuJoCo behavior; infrastructure errors never count as policy failures.”
3. **Ghost Case:** “Saved recipe, seed, controller digest and trace support exact replay of a specific failure.”
4. **Evidence:** “Observation, Nemotron interpretation and artifact verification are separate.”
5. **Compare:** “A new controller passes this tested case; this is not a general safety claim.”
6. **Reference:** “Public seed-42 MuJoCo trace; this reference has no Nemotron review and is excluded from customer scores.”

**Three-minute video outline:**

| Time | Record the actual module | Narration focus |
| --- | --- | --- |
| 0:00–0:20 | A measured failed trial and its state-derived replay | “This is a simulator trace, not footage of a physical robot.” |
| 0:20–0:45 | Create a CPU Hunt and click Release the Ghost | Executable controller, target task and bounded search budget. |
| 0:45–1:30 | Live trials, telemetry and search focus | Show real MuJoCo progression; keep at least one minute of key modules visibly operating. |
| 1:30–2:05 | Verified Ghost Case and exact replay | Recipe, digest, observed failure and repeatability limitations. |
| 2:05–2:30 | Completed Nemotron review **only if it exists in that signed-in run** | Cite the actual Token Factory model ID, evidence digest and token usage; never substitute a contract test. |
| 2:30–2:55 | Compatible-controller regression and close | Passing one case is not a safety certificate; show the honest result. |

The official rules call for a public video under three minutes and at least one minute of actual application modules in action for a software-only Physical AI entry. Do not use a landing-page animation or generated hazard clip as a substitute for controller execution. See [the official rules](https://nebiusglobalaihackathon.devpost.com/rules).

## Evidence and reproducibility notes for judges

**Public, inspectable CPU reference:** [index](https://ghost-trials.netlify.app/assets/reference/gantry-v1/index.json), [telemetry](https://ghost-trials.netlify.app/assets/reference/gantry-v1/telemetry.jsonl), [recipe](https://ghost-trials.netlify.app/assets/reference/gantry-v1/recipe.json), [manifest](https://ghost-trials.netlify.app/assets/reference/gantry-v1/manifest.json), [trajectory](https://ghost-trials.netlify.app/assets/reference/gantry-v1/trajectory.svg). This separately generated seed-42 run is **not** the model-reviewed acceptance trial. It is excluded from all customer results and scores.

**Observed local validation:** a 16-trial adaptive MuJoCo Hunt found three failures; a saved case replayed at 0.625826 m and a candidate controller reached 0.776821 m on the same case. A separate live-reviewed seed-42 trial reached 0.729056 m, passed trace verification and received the Nemotron Super review described above. The operator acceptance output was local, not a publicly archived raw evidence bundle. Independent human robotics review, video decoding and hardware attestation were **not** performed for that CPU trial. The trajectory SVG is derived from states, not video.

**Run locally:** follow the [README](https://github.com/linoxbt/ghost-trials#quick-start), then run `uv run python -m scripts.cpu_smoke --strategy grid --trials 9 --output data/cpu-validation` for actual headless MuJoCo trials, exact replay and regression. Tests: `uv run --frozen --extra dev --extra physics --extra models --extra storage pytest -q`. The default CPU path needs no GPU or paid API. To add a live model review, use only the backend configuration and spending safeguards in the README; a customer's organization needs an explicit budget allocation.

**Known limits:** The default task is a gantry manipulation benchmark, not Unitree G1 locomotion. The built-in lightweight neural-policy format is executable on CPU but is not a trained G1 checkpoint. Physical recording support has only fixture-level validation. No live Cosmos video, G1/SONIC/GR00T execution, Isaac worker acceptance, independent safety certification, or physical robot result is represented as complete. An application admission budget is not an external provider charge ceiling. Results are conditional on the tested controller, simulator version, recipe, seed, task and metric definition.

## Final owner checklist

- [ ] Confirm the **project name is Ghost Trials** in the Devpost overview.
- [ ] Confirm your actual residence, age/eligibility, team status, project start date and any Builders & Brews attendance.
- [ ] Choose the three personal 1–10 ratings; do not present them as measured benchmark scores.
- [ ] Sign in to the hosted site, run a fresh Hunt, inspect one Ghost Case and check the exact replay/regression flow.
- [ ] If the video claims a live Nemotron review in the signed-in app, have an operator allocate only your workspace an admission budget and verify `model_review.status=complete` on that exact trial.
- [ ] Record and upload a public YouTube video under three minutes, including at least one minute of real key modules operating.
- [ ] Verify the live URLs, public repository, MIT license, README, media captions and feedback fields immediately before pressing Submit.

This dossier prepares submission text; it does not submit the project, attest eligibility, guarantee prize eligibility, or turn bounded simulator evidence into a robot-safety certificate.
