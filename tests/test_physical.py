"""Synthetic fixture recordings test contracts; these are NOT hardware runs."""
import hashlib
import json
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from test_accounts import identities, signin
from ghost_trials.models import JudgeResult, TrialStatus
from ghost_trials.physical import CaptureMetadata, FILES, RecordingSetup, VERSION, verify_recording
from workers.physical.capture_g1 import G1Observer

ORIGIN = {"Origin": "https://console.test"}
DIGEST = "sha256:" + "a"*64


@pytest.fixture
def fixture_bundle(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Physical media validation requires ffmpeg and ffprobe")
    root = tmp_path / "fixture_not_hardware"
    root.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=orange:s=64x64:r=20",
        "-t", "1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "response.mp4")],
        check=True, capture_output=True, timeout=15)
    setup = {"prompt": "Fixture only: observe a supervised walking task", "policy_name": "fixture-policy",
        "checkpoint_digest": DIGEST, "robot_serial": "fixture-not-a-robot", "robot_variant": "g1_29dof",
        "severity": "low", "hazard_type": "path_obstruction", "on_site_operator_confirmed": True}
    metadata = CaptureMetadata(schema_version=VERSION, robot_serial=setup["robot_serial"], robot_variant="g1_29dof",
        checkpoint_digest=DIGEST, controller_name=setup["policy_name"], observer_only=True,
        operator_confirmed_physical_hardware=True, clock_basis="capture_host_monotonic",
        video_offset_ms=0.0, video_sync_uncertainty_ms=50.0, command_change_threshold_rad=.03,
        clearance_method="external tracker fixture", calibration_id="fixture-not-calibrated-hardware")
    (root / "capture.json").write_text(metadata.model_dump_json())
    rows = [{"timestamp_ms": float(i*100), "state_age_ms": 0.0, "command_age_ms": 0.0,
        "joint_positions_rad": [0.0]*29, "imu_rpy_rad": [0.0]*3,
        "policy_command_rad": ([0.1]+[0.0]*28) if i>=2 else [0.0]*29,
        "hazard_active": i>=1, "task_completed": i==10, "collision_observed": False,
        "fall_observed": False, "intervention_active": False, "clearance_m": .7} for i in range(11)]
    (root / "telemetry.jsonl").write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    return root, setup, rows


def manifest(root):
    return {name: {"bytes": (root/name).stat().st_size, "sha256": hashlib.sha256((root/name).read_bytes()).hexdigest()} for name in FILES}


def test_video_trace_and_independent_recomputation(fixture_bundle):
    root, setup, _ = fixture_bundle
    metrics, verification = verify_recording(root, RecordingSetup(**setup), manifest(root))
    assert metrics.time_to_react_ms == 100 and metrics.min_clearance_m == .7
    assert metrics.evidence_origin == "physical" and metrics.measurements_are_proxies
    assert verification["video_decoded"] is True and verification["hardware_execution_attested"] is False
    assert metrics.hardware_provenance["verification"] == "operator_declared_not_attested"


@pytest.mark.parametrize("failure", ["identity", "clock", "gap", "nan", "boolean", "calibration", "baseline", "video", "hash", "symlink"])
def test_bad_recordings_fail_closed(fixture_bundle, failure):
    root, setup, rows = fixture_bundle
    if failure == "identity": setup["robot_serial"] = "different-robot"
    elif failure == "clock": rows[2]["timestamp_ms"] = rows[1]["timestamp_ms"]
    elif failure == "gap": rows.pop(4); rows.pop(4)
    elif failure == "nan": rows[2]["joint_positions_rad"][0] = float("nan")
    elif failure == "boolean": rows[2]["fall_observed"] = "false"
    elif failure == "baseline": rows[0]["policy_command_rad"] = None
    elif failure == "video": (root/"response.mp4").write_bytes(b"not a recording")
    elif failure == "calibration":
        metadata = json.loads((root/"capture.json").read_text()); metadata["calibration_id"] = None
        (root/"capture.json").write_text(json.dumps(metadata))
    elif failure == "symlink":
        video = root/"response.mp4"; target=root/"original.mp4"; video.rename(target); video.symlink_to(target)
    (root/"telemetry.jsonl").write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    records = manifest(root)
    if failure == "hash": records["telemetry.jsonl"]["sha256"] = "0"*64
    with pytest.raises((ValueError, KeyError)):
        verify_recording(root, RecordingSetup(**setup), records)


@pytest.fixture
def physical_api(identities, monkeypatch):
    app, access, store, settings, token = identities
    settings.ghost_artifact_root.mkdir(parents=True)
    monkeypatch.setattr(settings, "ghost_physical_disk_reserve_bytes", 10485760)
    return app, access, store, settings, token


async def upload(client, session, root):
    route = "/physical/sessions/" + session["session_id"]
    response = await client.put(route+"/manifest", json=manifest(root), headers=ORIGIN)
    assert response.status_code == 200, response.text
    for name in sorted(FILES):
        data = (root/name).read_bytes()
        headers = {**ORIGIN, "Content-Range": f"bytes 0-{len(data)-1}/{len(data)}"}
        response = await client.put(route+"/artifacts/"+name, content=data, headers=headers)
        assert response.status_code == 200 and response.json()["sha256_matches"]
        # Retrying an identical chunk is safe, not an overwrite.
        assert (await client.put(route+"/artifacts/"+name, content=data, headers=headers)).status_code == 200
    return route


@pytest.mark.asyncio
async def test_plan_without_hardware_and_update_readiness(physical_api, fixture_bundle):
    app, _, _, _, token = physical_api
    root, setup, _ = fixture_bundle
    plan = {**setup, "on_site_operator_confirmed": False, "robot_variant": "unconfirmed", "checkpoint_digest": None, "robot_serial": None}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.post("/physical/sessions", json=plan, headers=ORIGIN)).status_code == 401
        await signin(client, token())
        response = await client.post("/physical/sessions", json=plan, headers=ORIGIN)
        assert response.status_code == 201
        session = response.json(); route="/physical/sessions/"+session["session_id"]
        assert session["robot_commands_enabled"] is False and session["trial_id"] is None
        assert (await client.put(route+"/manifest", json=manifest(root), headers=ORIGIN)).status_code == 409
        assert (await client.patch(route+"/setup", json=setup, headers=ORIGIN)).status_code == 200
        await upload(client, session, root)
        assert (await client.patch(route+"/setup", json=setup, headers=ORIGIN)).status_code == 409
        assert (await client.post(route+"/validate", headers=ORIGIN)).status_code == 200


@pytest.mark.asyncio
async def test_private_recording_upload_playback_and_judge_gate(physical_api, fixture_bundle):
    app, access, store, settings, token = physical_api
    root, setup, _ = fixture_bundle
    transport = httpx.ASGITransport(app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as alice, httpx.AsyncClient(transport=transport, base_url="http://test") as bob:
        await signin(alice, token()); await signin(bob, token("bob"))
        session = (await alice.post("/physical/sessions", json=setup, headers=ORIGIN)).json()
        route = await upload(alice, session, root)
        for method, path, kwargs in [("GET", route, {}), ("PUT", route+"/manifest", {"json": manifest(root)}),
            ("POST", route+"/validate", {})]:
            assert (await bob.request(method, path, headers=ORIGIN, **kwargs)).status_code == 404
        assert (await bob.get("/physical/sessions")).json() == []
        response = await alice.post(route+"/validate", headers=ORIGIN)
        assert response.status_code == 200, response.text
        validated = response.json(); tid=validated["trial_id"]
        assert len(store.trials) == 1 and store.trials[tid].status == TrialStatus.RECORDED
        assert (await alice.post(route+"/validate", headers=ORIGIN)).json()["trial_id"] == tid
        assert (await alice.get(route+"/artifacts/response.mp4")).status_code == 200
        assert (await bob.get(route+"/artifacts/response.mp4")).status_code == 404
        assert (await bob.get("/trials/"+tid)).status_code == 404
        assert (await alice.post(route+"/judge", headers=ORIGIN)).status_code == 503
        assert store.trials[tid].score_category is None and not store.job(tid)
        assert (await alice.post("/trials/"+tid+"/replay", headers=ORIGIN)).status_code == 409
        assert (await alice.post(route+"/move", headers=ORIGIN)).status_code == 404


@pytest.mark.asyncio
async def test_paid_physical_judge_uses_recording_not_simulation(physical_api, fixture_bundle, monkeypatch):
    app, access, store, settings, token = physical_api
    from ghost_trials.app import pipeline
    class NoRobotOperation:
        async def generate(self, *args): pytest.fail("Must not generate a video for an uploaded recording")
        async def run(self, *args): pytest.fail("Must not execute a simulator or robot")
    class JudgeFixture:
        async def judge(self, scenario, metrics):
            assert metrics.evidence_origin == "physical"
            return JudgeResult(score_category="avoided", confidence=.99, reasoning_trace="Fixture model interpretation", tier_used="test-fixture-not-real-Nemotron")
    monkeypatch.setattr(pipeline, "generator", NoRobotOperation()); monkeypatch.setattr(pipeline, "simulator", NoRobotOperation())
    monkeypatch.setattr(pipeline, "judge", JudgeFixture())
    for key, value in {"ghost_judge_provider":"nebius", "ghost_live_execution_enabled":True,
        "ghost_provider_spending_controls_confirmed":True,"ghost_platform_budget_cents":10000,
        "ghost_live_job_reservation_cents":100}.items(): monkeypatch.setattr(settings, key, value)
    root, setup, _ = fixture_bundle
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        org = await signin(client, token()); access.accounts.allocate_budget(org, 1000)
        session = (await client.post("/physical/sessions", json=setup, headers=ORIGIN)).json()
        route = await upload(client, session, root)
        tid = (await client.post(route+"/validate", headers=ORIGIN)).json()["trial_id"]
        assert (await client.post(route+"/judge", headers=ORIGIN)).status_code == 202
        await pipeline.run(tid)
        assert store.trials[tid].status == TrialStatus.DONE
        assert store.trials[tid].score_category.value == "insufficient_evidence"
        # Repeated admission must not reserve budget twice.
        assert (await client.post(route+"/judge", headers=ORIGIN)).status_code == 202
        assert access.accounts.budget(org)["used_cents"] == 100


def test_observer_reads_feedback_and_commands_without_actuation():
    observer = G1Observer.__new__(G1Observer)
    observer.lock = threading.Lock(); observer.state = observer.command = None
    with pytest.raises(RuntimeError): observer.sample()
    observer.on_state(SimpleNamespace(motor_state=[SimpleNamespace(q=.2)]*29, imu_state=SimpleNamespace(rpy=[.1,.2,.3])))
    observer.on_command(SimpleNamespace(motor_cmd=[SimpleNamespace(q=.4)]*29))
    row = observer.sample()
    assert row["joint_positions_rad"] == [.2]*29 and row["policy_command_rad"] == [.4]*29
    observer.command = (time.monotonic()-1, [.4]*29)
    assert observer.sample()["policy_command_rad"] is None
    observer.state = (time.monotonic()-1, [.2]*29, [.1,.2,.3])
    with pytest.raises(RuntimeError): observer.sample()


@pytest.mark.asyncio
async def test_chunk_limits_and_private_viewer_permissions(physical_api, fixture_bundle, monkeypatch):
    app, access, store, settings, token = physical_api
    root, setup, _ = fixture_bundle
    monkeypatch.setattr(access, "tokens", {"admin":"p"*48,"viewer":"v"*48})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.post("/physical/sessions", json=setup,
            headers={"Authorization":"Bearer "+"v"*48})).status_code == 403
        await signin(client, token())
        session=(await client.post("/physical/sessions", json=setup, headers=ORIGIN)).json()
        route="/physical/sessions/"+session["session_id"]
        assert (await client.put(route+"/manifest", json=manifest(root), headers=ORIGIN)).status_code == 200
        assert (await client.put(route+"/artifacts/response.mp4", content=b"x"*262145,
            headers={**ORIGIN,"Content-Range":"bytes 0-262144/262145"})).status_code == 413
        assert (await client.put(route+"/setup", content=b"x"*16385,headers=ORIGIN)).status_code == 413
        monkeypatch.setattr(settings,"ghost_physical_max_chunks_per_minute",2)
        # Fresh window key, independent of ordinary mutations.
        with store.connect() as db:
            db.execute("DELETE FROM rate_limits WHERE key LIKE 'recording-upload:%'")
        data=(root/"response.mp4").read_bytes(); headers={**ORIGIN,"Content-Range":f"bytes 0-{len(data)-1}/{len(data)}"}
        for _ in range(2):
            assert (await client.put(route+"/artifacts/response.mp4",content=data,headers=headers)).status_code == 200
        response=await client.put(route+"/artifacts/response.mp4",content=data,headers=headers)
        assert response.status_code == 429 and response.headers['retry-after']=='60'


def test_physical_observer_has_no_motor_publishers():
    import ast
    import inspect
    from workers.physical import capture_g1
    tree=ast.parse(inspect.getsource(capture_g1))
    names=[alias.name for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) for alias in node.names]
    assert "ChannelSubscriber" in names and "ChannelPublisher" not in names
    assert not any(isinstance(n,ast.Attribute) and n.attr in {"Write","ReleaseMode","SetVelocity"} for n in ast.walk(tree))
    with pytest.raises(ValueError): G1Observer("lo")
