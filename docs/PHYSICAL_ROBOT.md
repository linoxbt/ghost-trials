# Physical robot recording handoff

This implements **recording and evaluation of an externally running policy**.
It is not an autonomous controller deployment, remote motor-control service,
emergency stop, hardware attestation, or safety certification. There are no
robot movement endpoints. No physical robot has been tested from this workspace.

## Prepare now, without hardware

Open `/app/#/physical`. Create a capture plan. Leave hardware compatibility
unconfirmed, the robot serial/checkpoint blank, and on-site confirmation unchecked.
This saves a private organization-owned session without starting a robot or model
inference. Download its setup JSON for the future on-site operator.

The observer initially targets the G1 **29-DOF** SDK2 message layout. Compatibility
with the specific variant, firmware, controller, and SDK revision must be checked
on site. Do not select compatibility merely to bypass the upload gate.

## Before recording on site

- Obtain authorized robot access and qualified on-site supervision.
- Establish the local physical emergency-stop procedure and controlled test area.
- Independently validate the selected GR00T/SONIC policy and compatible weights
  using the vendor deployment instructions before any live task.
- Verify the checkpoint digest against the running policy, the actual robot serial,
  DDS topics, joint mapping, firmware, and camera device.
- Start with a stationary or otherwise approved low-risk recording. This app must
  not be used to automatically stage falling-object, slippery-floor or human hazards.
- Account for privacy and permission when recording people or a facility.

NVIDIA's workflow:
https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vla_workflow.html

Unitree SDK2 Python:
https://github.com/unitreerobotics/unitree_sdk2_python

Install the locally validated SDK revision on the capture machine following its
official instructions. The backend does not install robot SDKs or activate motors.
The camera host needs FFmpeg; the backend needs both `ffmpeg` and `ffprobe`.

Edit the prepared session to supply confirmed identity, compatible variant,
policy name/digest and on-site confirmation. Download the updated setup.

## Read-only observer and actual camera capture

From the checked-out project on the on-site machine:

```
python -m workers.physical.capture_g1 \
  --setup /path/to/phy_session-setup.json \
  --output /path/to/new-recording-directory \
  --interface <physical-robot-network-interface> \
  --camera-device /dev/video0 \
  --duration 60 \
  --confirm-on-site
```

The observer subscribes to `rt/lowstate` and `rt/lowcmd`. It does not publish
commands, release control modes, deploy a controller, or generate a hazard.
An approved policy must already be running under the on-site operator's control.
If no fresh robot state or policy-command stream is available, recording fails
instead of synthesizing data. Other controller topics/layouts need local validation
and an adapter update before use. Loopback is rejected in the physical observer.

Type observed-event markers in its terminal: `onset`, `complete`, `collision`,
`fall`, `intervention`, `resumed`, `stop`. Mark **observations**, not desired outcomes.
Record a pre-onset baseline. Keep recording long enough to capture the outcome.
Stopping this recorder **does not stop the robot**; use the local safety procedure.

The camera is recorded as a real V4L2 stream, not generated video. Camera-to-trace
alignment currently uses the camera-launch time with declared 500 ms uncertainty.
Check alignment on site; this is not hardware-triggered frame synchronization.

## What is measured, and what is not

- Joint state and IMU: SDK2 feedback, sampled at approximately 50 Hz with freshness
  checks. Capture loss/gaps beyond the validation tolerance fail validation.
  Timestamps and freshness use host receipt time, not a synchronized robot clock.
- Policy commands: observed low-level joint targets; association with GR00T/SONIC
  is operator-declared, not cryptographically attested.
- Timing: first observed command change relative to the pre-onset command baseline.
  This is a **reaction proxy**. Ordinary walking can change commands without hazard
  recognition; the UI and judge must retain that limitation.
- Outcomes: on-site operator observations, not an autonomous collision detector.
- Clearance: absent by default. The SDK joint/IMU stream does not measure nearest
  obstacle surface distance. Supply independently measured, calibrated sensor
  values through a validated local sensor adapter before drawing clearance claims.
  Metadata must name the measurement method and calibration reference. Do not
  populate clearance using generated video, model guesses, or simulation output.
- Physical friction and contact slip: not inferred by this observer. A physical
  traction study needs appropriate calibrated sensors and an approved protocol.

## Upload and inspect

Select exactly `response.mp4`, `telemetry.jsonl`, `capture.json` from the completed
directory in Physical recordings. The dashboard calculates SHA-256 values,
uploads in 256 KiB resumable chunks, then requests validation. Re-select the same
files after a network interruption; conflicting retries are rejected.
Uploads have a separate bounded request-rate allowance; the dashboard pauses on
429 responses. It never automatically retries a possibly billed model operation.

Validation verifies the sealed artifact manifest, checkpoint/session identity,
strict timestamp/sample freshness, video coverage within declared timing
uncertainty, full video decoding, and command-timing/clearance recomputation.
It does **not** prove that an operator-supplied bundle came from physical hardware.
Successful uploads create a `recorded` trial with camera playback and measured
data, but no invented finding or safety score. Physical and simulator records
remain separate cohorts; physical recordings do not get a repeatable simulator seed.
For API compatibility, the legacy `simulation_video_url` metric field points to
the uploaded camera MP4 in physical mode; `execution_mode` and `evidence_origin`
identify the source. This does not mean the physical clip was simulated.

For an existing private-team operator token, a CLI uploader is also available:

```
# Set GHOST_BACKEND_URL and GHOST_RECORDING_UPLOAD_TOKEN privately first.
python -m scripts.upload_physical_recording phy_<session-id> /path/to/recording
```

The CLI never enables judging or motion. Individual Privy-account users should
use their authenticated dashboard; don't share organization-owner sessions or
put tokens in shell arguments, screenshots, source control, or frontend variables.

## Real judge, separately authorized

“Request real judge” queues Nebius Nemotron only after the existing live-execution
enablement and platform/organization admission budgets pass. It does not require
Cosmos generation or a simulator worker for an already captured recording. The
queue re-verifies the bundle before inference and never generates or executes a robot
in this path. Two Super passes may escalate to Ultra; provider charges can apply.

Operator-declared physical provenance and reaction proxies require review. The
guardrail keeps such results `insufficient_evidence`, while preserving the judge's
original interpretation and observed measurements. This is intentional—not a
claim that the measured values are fake, and not a safety certification.

## API

- `GET /physical/capabilities`
- `GET, POST /physical/sessions`
- `GET /physical/sessions/{id}`
- `PATCH /physical/sessions/{id}/setup` (before the manifest is sealed)
- `PUT /physical/sessions/{id}/manifest`
- `PUT /physical/sessions/{id}/artifacts/{name}` with `Content-Range`
- `POST /physical/sessions/{id}/validate`
- `GET /physical/sessions/{id}/artifacts/{name}` (validated, private)
- `POST /physical/sessions/{id}/judge`
- `POST /physical/sessions/{id}/cancel` (pending sessions only)

Viewer roles cannot modify/upload/judge. Cross-organization IDs and artifacts
return 404. Uploads are bounded by a bundle limit and disk reserve. Cancelled
recording files are retained privately, not deleted. Backup includes this evidence.
Production deployments must account for upload storage, retention policies,
request limits at their reverse proxy, and current FFmpeg security updates.
