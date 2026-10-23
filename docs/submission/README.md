# Ghost Trials — Devpost submission package

**Superseded working drafts (October 16, 2026).** Use the current root [submission.md](../../submission.md) for Devpost text and [submission.pdf](../../submission.pdf) for the judge-facing technical dossier. The documents below predate the live Nemotron-reviewed CPU trial and should not be pasted into Devpost without reconciliation. G1/Cosmos integrations remain unvalidated.

## Project overview

### Project name — paste this

Ghost Trials

The existing Devpost draft is named “Onvara.” Change that field to Ghost Trials if this draft is for this repository. Do not use two names for the same application without explaining their relationship.

### Elevator pitch — paste this

Ghost Trials autonomously hunts for failures in executable robot controllers, verifies and replays the evidence, and compares the next controller—without claiming safety certification.

This pitch is within the 200-character field shown in the supplied form.

## Project details

- **About the project:** copy the complete [Project Story](PROJECT_STORY.md). It includes inspiration, implementation, challenges, learning, achievements and next steps.
- **Built with:** Python, FastAPI, Pydantic, SQLite, JavaScript, HTML, CSS, React, Privy, WebSockets, NVIDIA Nemotron, Nebius Token Factory, HTTPX, Docker, MuJoCo, Pytest, GitHub.
- These tags describe software used in the implementation or tests. Do not add Isaac Sim, Isaac Lab-Arena, GR00T, GEAR-SONIC or Cosmos as demonstrated execution technologies until the corresponding stage actually runs. Their integration code and intended roles are described in the story instead.

### “Try it out” links

Public source: [Ghost Trials on GitHub](https://github.com/linoxbt/ghost-trials).

Hosted application: [Ghost Trials](https://ghosttrials.site/). The FastAPI CPU backend runs in Docker behind Caddy on a self-hosted VPS (`https://backend.ghosttrials.site`). Sign in with the site's existing Privy flow to start a Hunt.

Before submission, test sign-in and a fresh Hunt through the hosted site on desktop and mobile. New users receive isolated workspaces; historical fixtures remain explicitly labeled. The optional Nebius reviewer must be enabled under a confirmed spending control and shown in a genuine verified trial before claiming runtime model use. Do not paste account secrets or shared administrator tokens into the public story.

### Project media

Use up to four carefully selected screenshots rather than repeating the same page:

1. A genuine CPU Hunt timeline with measured passes, failures, repeats and the bounded search map.
2. A Ghost Case showing the stored recipe, verification, reproduction status and observed boundary if one was established.
3. A trial's telemetry-derived state replay beside its measured task result and separate Nemotron interpretation, only if a live model call completed.
4. A matched controller regression with an honest result, including “still failing” when applicable.

For the thumbnail, use the orange Ghost Trials logo and a readable title: “Evidence before confidence.” Export JPG/PNG/GIF below 5 MB with a 3:2 aspect ratio, as requested by the form. Remove account names, credentials and private customer data from screenshots. Do not use generated humanoid illustrations as if they were recorded robot trials.

### Video demo link

`[PUBLIC_YOUTUBE_VIDEO_URL]`

The video has not been recorded or uploaded by writing this package. See the [demo script](DEMO_SCRIPT.md). The official rules require a public YouTube video under three minutes; for Physical AI, include at least one minute of hardware operation or, when there is no hardware component, key application modules actually running. Do not describe fixture animation as policy execution. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules).

## Additional info

Use [Additional Info](ADDITIONAL_INFO.md) for field-by-field technical answers and personal-field guidance. Replace every owner-confirmation placeholder before submitting. Rating suggestions are not fabricated benchmark results, and this package does not complete legal attestations on your behalf.

## Optional file upload

The form permits a file up to 35 MB. You may attach these Markdown documents or a small PDF export with the architecture, current evidence status and reproducibility instructions. No upload is necessary merely because the field is shown. Never include `.env`, private access tokens, recordings without permission, model weights without redistribution rights, SQLite user databases or account exports.

## Before selecting Submit

- Confirm the project name, submitter identity, residence, team eligibility and actual start date.
- Complete the video and source-code requirements; verify the public repository contains its MIT license and current run instructions.
- Verify that the application's runtime demonstration includes the claimed Nebius/NVIDIA model use. A saved connectivity result alone is not proof of the entire robot pipeline.
- The CPU Hunt already produces recorded policy-controller telemetry; verify a fresh deployed run and, before claiming live model-assisted trial review, capture one completed Nebius review of verified evidence.
- Verify the hosted demo link and provide normal user sign-in instructions. Do not publish a shared administrator token or bypass the existing authentication flow.
- Review [evidence status](EVIDENCE_STATUS.md) and [submission evidence checklist](../SUBMISSION_EVIDENCE.md).
- Keep model ratings, model-comparison answers and user-experience feedback faithful to tests you actually performed.

This is a prepared submission package, not a completed Devpost submission, eligibility approval, guarantee of acceptance, or prediction of winning.
