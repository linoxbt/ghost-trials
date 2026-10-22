"""Organization-private hardware recording API; intentionally no motion routes."""
import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .evaluation import RUBRIC_VERSION
from .models import LiveEvent, Scenario, StructuredDescription, Trial, TrialStatus
from .physical import FILES, FileManifest, RecordingSetup, file_digest, verify_recording


def append_chunk(path, data):
    with path.open("ab" if path.exists() else "xb") as stream:
        os.chmod(path, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def build_router(settings, store, access, publish, submission_allowed):
    router = APIRouter(prefix="/physical", tags=["Physical recordings (read-only hardware)"])
    lock = asyncio.Lock()  # session creation and per-organization session limits
    session_locks: dict[str, asyncio.Lock] = {}

    def session_lock(session_id: str) -> asyncio.Lock:
        # One recording's chunked upload or validation never blocks another organization's uploads.
        if not re.fullmatch(r"phy_[a-f0-9]{24}", session_id):
            raise HTTPException(404, "Recording session not found")
        return session_locks.setdefault(session_id, asyncio.Lock())

    def principal(request, write=False):
        if write and not access.enabled:
            raise HTTPException(401, "Authenticated recording upload is required")
        access.require(request, ("admin", "operator") if write else ("admin", "operator", "viewer"))
        return access.principal(request)

    def save(session):
        with store.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES('physical_session',?,?)",
                       (session["session_id"], json.dumps(session)))

    def load(session_id, request, write=False):
        owner = principal(request, write)
        with store.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind='physical_session' AND id=?", (session_id,)).fetchone()
        session = json.loads(row[0]) if row else None
        if not session or session["organization_id"] != owner.organization_id:
            raise HTTPException(404, "Recording session not found")
        return session

    def directory(session_id):
        if not re.fullmatch(r"phy_[a-f0-9]{24}", session_id):
            raise HTTPException(404, "Recording session not found")
        root = settings.ghost_artifact_root.resolve()
        raw = root / "physical" / session_id
        if any(p.is_symlink() for p in (raw, raw.parent)):
            raise HTTPException(409, "Unsafe recording storage")
        return raw

    def check_mutation():
        if store.maintenance():
            raise HTTPException(503, "Recordings paused for maintenance")

    @router.get("/capabilities")
    async def capabilities(request: Request):
        principal(request)
        return {"mode": "read_only_capture", "robot_commands_enabled": False,
            "supported_observer": "Unitree G1 29-DOF / SDK2 DDS subscribers",
            "physical_hardware_connected": False, "hardware_execution_attested": False,
            "upload_chunk_bytes": 262144, "maximum_bundle_bytes": settings.ghost_physical_max_bundle_bytes,
            "required_files": sorted(FILES), "requires_local_hardware_validation": True,
            "judge_provider": settings.ghost_judge_provider}

    @router.get("/sessions")
    async def sessions(request: Request):
        owner = principal(request)
        with store.connect() as db:
            rows = db.execute("SELECT payload FROM records WHERE kind='physical_session'").fetchall()
        return sorted([s for row in rows if (s := json.loads(row[0]))["organization_id"] == owner.organization_id],
                      key=lambda s: s["created_at"], reverse=True)

    @router.post("/sessions", status_code=201)
    async def create(body: RecordingSetup, request: Request):
        owner = principal(request, True)
        check_mutation()
        async with lock:
            with store.connect() as db:
                existing = [json.loads(row[0]) for row in db.execute("SELECT payload FROM records WHERE kind='physical_session'")]
            pending = [s for s in existing if s["status"] in {"awaiting_capture", "uploading"}]
            if len(pending) >= 10 or sum(s["organization_id"] == owner.organization_id for s in pending) >= 3:
                raise HTTPException(429, "Too many pending hardware recordings")
            session_id = "phy_" + uuid.uuid4().hex[:24]
            session = {"session_id": session_id, "organization_id": owner.organization_id,
                "created_by": owner.subject, "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "awaiting_capture", "setup": body.model_dump(mode="json"),
                "manifest": {}, "uploads": {}, "trial_id": None, "verification": None,
                "robot_commands_enabled": False, "hardware_execution_attested": False}
            directory(session_id).mkdir(parents=True, exist_ok=False, mode=0o700)
            save(session)
            store.audit("physical_session_prepared", owner.role, session_id,
                        organization_id=owner.organization_id, subject=owner.subject)
            return session

    @router.get("/sessions/{session_id}")
    async def get(session_id: str, request: Request):
        return load(session_id, request)

    @router.patch("/sessions/{session_id}/setup")
    async def setup(session_id: str, body: RecordingSetup, request: Request):
        principal(request, True)
        check_mutation()
        async with session_lock(session_id):
            session = load(session_id, request, True)
            if session["status"] != "awaiting_capture":
                raise HTTPException(409, "Uploaded recording identity is immutable")
            session["setup"] = body.model_dump(mode="json")
            save(session)
            return session

    @router.post("/sessions/{session_id}/cancel")
    async def cancel(session_id: str, request: Request):
        principal(request, True)
        async with session_lock(session_id):
            session = load(session_id, request, True)
            if session["status"] not in {"awaiting_capture", "uploading"}:
                raise HTTPException(409, "Only a pending recording can be cancelled")
            session["status"] = "cancelled"
            save(session)
            return session

    @router.put("/sessions/{session_id}/manifest")
    async def manifest(session_id: str, body: dict[str, FileManifest], request: Request):
        principal(request, True)
        check_mutation()
        if set(body) != FILES or sum(r.bytes for r in body.values()) > settings.ghost_physical_max_bundle_bytes:
            raise HTTPException(422, "Invalid file set or recording exceeds bundle limit")
        if body["capture.json"].bytes > 16384 or body["telemetry.jsonl"].bytes > 33554432:
            raise HTTPException(422, "Recording metadata or telemetry exceeds limits")
        async with session_lock(session_id):
            session = load(session_id, request, True)
            wanted = {k: v.model_dump() for k, v in body.items()}
            if session["manifest"] == wanted:
                return session
            setup = session["setup"]
            if (session["status"] != "awaiting_capture" or setup["robot_variant"] != "g1_29dof"
                    or not setup["on_site_operator_confirmed"] or not setup["robot_serial"] or not setup["checkpoint_digest"]):
                raise HTTPException(409, "Manifest is sealed or robot compatibility is unconfirmed")
            session.update(status="uploading", manifest=wanted)
            save(session)
            return session

    @router.put("/sessions/{session_id}/artifacts/{name}")
    async def upload(session_id: str, name: str, request: Request):
        principal(request, True)
        check_mutation()
        raw_range = request.headers.get("content-range", "")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", raw_range)
        if name not in FILES or not match or len(raw_range) > 80:
            raise HTTPException(422, "Known artifact and Content-Range are required")
        start, end, total = map(int, match.groups())
        data = await request.body()
        if not 0 < len(data) <= 262144 or end-start+1 != len(data) or start > end or end >= total:
            raise HTTPException(422, "Invalid upload chunk")
        async with session_lock(session_id):
            session = load(session_id, request, True)
            record = session["manifest"].get(name)
            if session["status"] != "uploading" or not record or total != record["bytes"]:
                raise HTTPException(409, "Artifact is sealed or does not match its manifest")
            path = directory(session_id) / name
            if path.is_symlink():
                raise HTTPException(409, "Unsafe artifact path")
            size = path.stat().st_size if path.exists() else 0
            if start < size:
                with path.open("rb") as stream:
                    stream.seek(start)
                    if stream.read(len(data)) != data:
                        raise HTTPException(409, "Retry conflicts with previously uploaded bytes")
            elif start != size:
                raise HTTPException(409, "Resume from the recorded byte offset")
            else:
                if shutil.disk_usage(directory(session_id)).free-len(data) < settings.ghost_physical_disk_reserve_bytes:
                    raise HTTPException(507, "Recording storage reserve reached")
                await asyncio.to_thread(append_chunk, path, data)
                size += len(data)
            session["uploads"][name] = {"received_bytes": size, "complete": size == total,
                "sha256_matches": size == total and await asyncio.to_thread(file_digest, path) == record["sha256"]}
            save(session)
            return session["uploads"][name]

    @router.post("/sessions/{session_id}/validate")
    async def validate(session_id: str, request: Request):
        principal(request, True)
        check_mutation()
        async with session_lock(session_id):
            session = load(session_id, request, True)
            if session["status"] == "validated":
                return session
            if session["status"] != "uploading" or any(not session["uploads"].get(n, {}).get("sha256_matches") for n in FILES):
                raise HTTPException(409, "Finish all verified artifact uploads first")
            root = directory(session_id)
            try:
                metrics, verification = await asyncio.to_thread(verify_recording, root,
                    RecordingSetup.model_validate(session["setup"]), session["manifest"])
            except (ValueError, KeyError, OSError, TypeError) as exc:
                raise HTTPException(422, "Hardware recording validation failed; check identity, timestamps, calibration and media") from exc
            except Exception as exc:
                raise HTTPException(422, "Video decoding failed or timed out; verify ffmpeg and the recording") from exc
            suffix = session_id[4:]
            scenario = Scenario(scenario_id="scn_"+suffix, organization_id=session["organization_id"],
                prompt=session["setup"]["prompt"], seed=0, severity_tag=session["setup"]["severity"],
                structured_description=StructuredDescription(objects=["physical G1"],
                    hazard_type=session["setup"]["hazard_type"], severity=session["setup"]["severity"],
                    expected_safe_behavior="Observe a supervised physical task; no hazardous action is requested by this app."))
            metrics.simulation_video_url = f"/physical/sessions/{session_id}/artifacts/response.mp4"
            metrics.trace_url = f"/physical/sessions/{session_id}/artifacts/telemetry.jsonl"
            trial = Trial(trial_id="trl_"+suffix, scenario_id=scenario.scenario_id,
                organization_id=session["organization_id"], status=TrialStatus.RECORDED,
                metrics=metrics, policy_name=session["setup"]["policy_name"], embodiment="UNITREE_G1_PHYSICAL_29DOF",
                rubric_version=RUBRIC_VERSION, execution_mode="physical", physical_session_id=session_id,
                evidence_verification=verification)
            session.update(status="validated", trial_id=trial.trial_id, verification=verification)
            # Session publication and trial creation are one durable transaction.
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                for kind, key, payload in (("scenario", scenario.scenario_id, scenario.model_dump_json()),
                                          ("trial", trial.trial_id, trial.model_dump_json()),
                                          ("physical_session", session_id, json.dumps(session))):
                    db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (kind, key, payload))
            store.scenarios[scenario.scenario_id], store.trials[trial.trial_id] = scenario, trial
            owner = principal(request)
            store.audit("physical_recording_validated", owner.role, session_id,
                        organization_id=owner.organization_id, subject=owner.subject)
            await publish(LiveEvent(trial_id=trial.trial_id, status=trial.status,
                message="Uploaded physical recording validated; no judge has run and hardware provenance is unverified"))
            return session

    @router.post("/sessions/{session_id}/judge", status_code=202)
    async def judge(session_id: str, request: Request):
        owner = principal(request, True)
        check_mutation()
        async with session_lock(session_id):
            session = load(session_id, request, True)
            if session["status"] != "validated":
                raise HTTPException(409, "Validate the recording first")
            if settings.ghost_judge_provider != "nebius":
                raise HTTPException(503, "A real Nebius judge must be configured")
            submission_allowed()
            original = store.trials[session["trial_id"]]
            if store.job(original.trial_id):
                return {"trial_id": original.trial_id, "status": original.status}
            trial = original.model_copy(update={"status": TrialStatus.QUEUED})
            try:
                store.enqueue_recording_judge(trial, settings.ghost_live_job_reservation_cents,
                                             settings.ghost_platform_budget_cents, owner.subject)
            except ValueError as exc:
                raise HTTPException(409, "Recording is already queued or admission budget is insufficient") from exc
            await publish(LiveEvent(trial_id=trial.trial_id, status=trial.status,
                                    message="Judge queued for uploaded recording; no robot motion requested"))
            return {"trial_id": trial.trial_id, "status": trial.status}

    @router.get("/sessions/{session_id}/artifacts/{name}")
    async def artifact(session_id: str, name: str, request: Request):
        session = load(session_id, request)
        if name not in FILES or session["status"] != "validated":
            raise HTTPException(404, "Validated artifact not found")
        path = directory(session_id) / name
        if path.is_symlink() or not path.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(path, headers={"Cache-Control": "private, no-store"})

    return router
