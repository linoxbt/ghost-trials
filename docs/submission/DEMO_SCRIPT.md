# Ghost Trials — live CPU Hunt demo runbook

Target: **2:45** total, public YouTube upload. The Physical AI rules call for at least one minute of key application modules actually running when no physical hardware is used. Record the real app and API; do not substitute a fixture, landing-page animation or generated scenario image for policy execution.

## Before recording

1. Use an isolated, signed-in workspace. Verify Netlify `/health` reports `cpu/mujoco_cpu/cpu`, and a three-trial test Hunt completes with trace-validated evidence.
2. If a real Nebius review will be shown, confirm credit-only use or a provider-side spending limit, set the application cap and organization budget, enable the reviewer, then verify one completed trial has `model_review.status=complete` with model ID, token usage and evidence digest. Otherwise **do not say that this video demonstrates runtime Nemotron**; the submission's required model-use claim remains unproven.
3. Run a disclosed, bounded adaptive Hunt budget large enough to show exploration, reproduction and an observed boundary when the trial outcomes support one. Do not promise a boundary in advance. Keep all original outcomes visible.
4. Select a Ghost Case with verified artifacts. Test the alternate controller on that exact case and record the real result—even if it still fails. Verify the export contains the matching recipe, seed, controller digests and simulator version.

## Screen and narration sequence

| Time | Actual screen action | Suggested narration |
|---|---|---|
| 0:00–0:20 | Open a measured failure and its telemetry-derived state replay. | “This controller failed a real MuJoCo physics trial. The animation is recorded simulator state, not camera footage or a generated robot video.” |
| 0:20–0:45 | Open Hunt creation: gantry robot, selected controller, tabletop task and bounded budget. Click **Release the Ghost**. | “Ghost Trials searches physical conditions that the simulator actually controls: mass, friction, block position and controller delay.” |
| 0:45–1:25 | Keep the live trial sequence and search map on screen as measured results arrive. | “The next candidate depends on earlier outcomes. Provider errors never count as policy failures.” |
| 1:25–2:00 | Open a verified Ghost Case; show exact replay, the same measured final position and an observed boundary if present. | “The saved recipe, seed, checkpoint digest, telemetry and hashes let us inspect and repeat this particular failure. The boundary describes only the tested region.” |
| 2:00–2:25 | Show the separate Nemotron panel **only after a live Token Factory request completed**. | “NVIDIA Nemotron on Nebius interprets verified measurements and cites supplied values. Its suggestion cannot overwrite the deterministic task result.” |
| 2:25–2:45 | Show the candidate-controller regression and honest result. | “The new controller was executed on the same case. Here it still fails, so we do not claim a fix or general safety.” |

If no live Nemotron review is obtained, replace that screen/narration with “Model review is not available for this run” and resolve the hackathon's model-runtime requirement before submission. A historic missing-evidence API diagnostic does not replace this trial-linked demonstration.

The owner must record/upload the video, confirm Devpost identity and eligibility fields, and add the public YouTube URL. Conceal credentials, personal emails and private workspaces. A video script is not proof of an executed trial or model call.
