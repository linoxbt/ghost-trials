# Ghost Trials — current-build video script

Target length: **2 minutes 45 seconds**. This script describes an honest current-build demonstration, not a completed GPU/hardware run. Do not film a fake “live robot trial.” Refresh the script after actual execution becomes available. Final Physical AI eligibility/competitiveness still depends on what the submitted project genuinely demonstrates.

The official rules require a public YouTube video under three minutes and at least one minute of hardware operation or, without a hardware component, key application modules in action. This storyboard reserves more than a minute for operating the existing application. It does not guarantee the organizers will accept an incomplete original pipeline. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules).

## 0:00–0:20 — The problem

Screen: actual dashboard overview. Keep the experimental-platform notice visible; do not hide the unavailable score.

Narration:

“A robot's response to an unexpected event matters, but a score without evidence can be misleading. Ghost Trials is an experimental evaluation workspace that brings trial records, telemetry, provenance and model-assisted review together. It is not a safety certificate.”

## 0:20–0:50 — Show what the records actually are

Screen: open Trial runs, select the Synthetic demo filter, then open one existing record. Show its explicit provenance banner and original finding.

Narration:

“These existing records are development fixtures, not measurements from a real robot. They remain inspectable, but none contributes to our experimental evaluation score. Missing provenance is labeled unverified, and absent eligible evidence produces an unavailable score—not an invented success.”

## 0:50–1:20 — Operate the evidence workflow

Screen: use the evidence inspector, expand artifact/limitation details, and export the reproducibility JSON. Open the exported JSON and highlight configuration, checkpoint identity, trace/video references and replay limitations. In a fixture, missing values must remain visible.

Narration:

“The report preserves what is known and what is missing: policy identity, scenario setup, measurement method, validation and artifact references. A recorded command change is not automatically hazard recognition. Hash checking is not proof of hardware execution. Reviewers can inspect these limits rather than accept the judge's narrative as a measurement.”

## 1:20–1:45 — Prepare for real evidence

Screen: Physical recordings. Prepare a capture plan with unknown serial/checkpoint left blank and on-site confirmation unchecked. Show that the plan is awaiting access, not a robot already connected. Do this in an explicitly designated demonstration workspace, not a real customer workspace.

Narration:

“We can prepare a recording plan while hardware access is pending. Our implemented G1 recorder is read-only: it is designed to observe feedback, externally issued commands and camera footage. Physical testing still needs a compatible robot, an approved running policy and an on-site operator. No robot motion is enabled from this page.”

## 1:45–2:15 — Explain the real Nebius/NVIDIA integration

Screen: sanitized model-connectivity evidence and the implementation of the judge's two-pass/escalation path. Label the saved result “Prior real inference diagnostic — no robot execution.” Do not display `.env`, tokens or raw authentication headers.

Narration:

“The implemented judge connects to NVIDIA Nemotron on Nebius Token Factory. It uses two Super passes and escalates disagreements or uncertain cases to Ultra. Real inference has been verified with a missing-evidence diagnostic, which returned insufficient evidence. This validates the model integration, not robot behavior. Live Cosmos generation and the GPU policy stack have not yet been demonstrated here.”

If you elect to film a fresh inference diagnostic, use the bounded provider-check command only after reviewing charges and explicitly authorizing that execution. Writing this script does not authorize or perform it. Label the diagnostic accurately and do not persist it as a robot trial.

## 2:15–2:45 — Close with the current milestone

Screen: dashboard pending real-trial milestone, then README/current status and public code repository.

Narration:

“The software workflow is implemented and covered by automated and mobile-browser tests. The next milestone is one actual policy execution with saved configuration, response video, telemetry, live Nemotron review and expert inspection. Ghost Trials' contribution is making the evidence and its limits visible—so confidence is earned from a recorded trial, not manufactured by an interface.”

## Once a genuine trial exists

Replace the fixture walkthrough with that specific trial. Show actual response footage, raw trace, the measured hazard-onset timeline, pinned checkpoint/configuration, artifact verification and the real model review. Identify the true backend: a SONIC/MuJoCo run must not be called Isaac Sim. Keep proxy and calibration limitations visible, and retain at least a minute of modules actually operating in the final video.

## Recording checklist

- Use readable text and spoken audio; keep the total below three minutes.
- Do not represent generated imagery, prerecorded diagnostics or synthetic clips as live robot operation.
- Get permission for any partner footage and avoid copyrighted audio/assets without authorization.
- Conceal credentials, private account details and confidential telemetry.
- Upload publicly to YouTube and replace `[PUBLIC_YOUTUBE_VIDEO_URL]` in the submission package.
- Update the project story and model feedback to match the exact demonstrated build.
