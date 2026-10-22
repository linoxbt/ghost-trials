import asyncio
import hashlib
import io
import tarfile

import httpx
import pytest

from ghost_trials.access_setup import prepare_access
from ghost_trials.backup import create_backup, restore_backup
from ghost_trials.config import Settings
from ghost_trials.durable import DurableStore
from ghost_trials.jobs import JobRunner
from ghost_trials.models import ScenarioCreate, TrialStatus
from ghost_trials.pipeline import CertificationPipeline
from ghost_trials.adapters import LocalScenarioGenerator, DeterministicIsaacSimulator, LocalRubricJudge
from ghost_trials.release_gate import release_report, decode_video
from ghost_trials.security import AccessControl


def local_pipeline(store):
    async def publish(event):
        pass
    return CertificationPipeline(store, LocalScenarioGenerator(), DeterministicIsaacSimulator(), LocalRubricJudge(), publish, 0)


@pytest.fixture
def private_api(monkeypatch, tmp_path):
    from ghost_trials.app import access, settings, store, app
    tokens = {"admin": "a" * 48, "operator": "o" * 48, "viewer": "v" * 48}
    monkeypatch.setattr(access, "enabled", True)
    monkeypatch.setattr(access, "tokens", tokens)
    monkeypatch.setattr(settings, "ghost_allowed_origins", "https://console.test")
    monkeypatch.setattr(settings, "ghost_cookie_secure", False)
    monkeypatch.setattr(store, "path", tmp_path / "api.sqlite3")
    monkeypatch.setattr(store, "scenarios", {})
    monkeypatch.setattr(store, "trials", {})
    return app, settings, store, tokens


@pytest.mark.asyncio
async def test_private_api_permissions_and_protected_evidence(private_api):
    app, _, store, tokens = private_api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/trials")).status_code == 401
        assert (await client.get("/generated/private.mp4")).status_code == 401
        viewer = {"Authorization": "Bearer " + tokens["viewer"]}
        assert (await client.get("/trials", headers=viewer)).status_code == 200
        assert (await client.get("/ops/audit", headers=viewer)).status_code == 403
        assert (await client.post("/scenarios", headers=viewer, json={"prompt": "A box falls suddenly"})).status_code == 403
        assert not store.trials


@pytest.mark.asyncio
async def test_sessions_origin_checks_and_cookie_security(private_api):
    app, _, _, tokens = private_api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        payload = {"token": tokens["operator"]}
        assert (await client.post("/auth/session", json=payload)).status_code == 403
        origin = {"Origin": "https://console.test"}
        assert (await client.post("/auth/session", headers=origin, json={"token": "wrong"})).status_code == 401
        login = await client.post("/auth/session", headers=origin, json=payload)
        assert login.status_code == 303
        assert "HttpOnly" in login.headers["set-cookie"]
        assert (await client.get("/auth/me")).json()["role"] == "operator"
        assert (await client.post("/scenarios", json={"prompt": "A box falls suddenly"})).status_code == 403
        assert (await client.post("/scenarios", headers=origin, json={"prompt": "A box falls suddenly"})).status_code == 202
        assert (await client.post("/auth/logout", headers=origin)).status_code == 200
        assert (await client.get("/trials")).status_code == 401


@pytest.mark.asyncio
async def test_idempotency_quotas_and_cancellation(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    headers = {"Authorization": "Bearer " + tokens["operator"], "Idempotency-Key": "trial-one"}
    body = {"prompt": "A box falls suddenly", "seed": 42}
    monkeypatch.setattr(settings, "ghost_max_pending_jobs", 1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        first = await client.post("/scenarios", json=body, headers=headers)
        assert first.status_code == 202
        trial_id = first.json()["trial"]["trial_id"]
        repeated = await client.post("/scenarios", json=body, headers=headers)
        assert repeated.json()["trial"]["trial_id"] == trial_id
        assert len(store.trials) == 1
        assert (await client.post("/scenarios", json={"prompt": "A different box falls"}, headers=headers)).status_code == 409
        no_key = {"Authorization": headers["Authorization"]}
        assert (await client.post("/scenarios", json=body, headers=no_key)).status_code == 429
        assert (await client.post(f"/trials/{trial_id}/cancel", headers=no_key)).status_code == 200
        assert store.job(trial_id)["state"] == "cancelled"
        assert store.trials[trial_id].error == "Cancelled before execution"


@pytest.mark.asyncio
async def test_live_execution_is_fail_closed_and_body_is_bounded(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    headers = {"Authorization": "Bearer " + tokens["operator"]}
    monkeypatch.setattr(settings, "ghost_judge_provider", "nebius")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.post("/scenarios", headers=headers, json={"prompt": "A box falls suddenly"})).status_code == 503
        assert (await client.post("/scenarios", headers=headers, content=b"x" * 17000)).status_code == 413
        assert not store.trials


@pytest.mark.asyncio
async def test_rate_limit_survives_new_store(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    monkeypatch.setattr(settings, "ghost_max_requests_per_minute", 1)
    headers = {"Authorization": "Bearer " + tokens["operator"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.post("/scenarios", headers=headers, json={"prompt": "A box falls suddenly"})).status_code == 202
        assert (await client.post("/scenarios", headers=headers, json={"prompt": "A box falls suddenly"})).status_code == 429
    assert not DurableStore(store.path).rate_allowed("mutation:operator", 1)


@pytest.mark.asyncio
async def test_maintenance_is_admin_only_and_survives_restart(private_api):
    app, _, store, tokens = private_api
    admin = {"Authorization": "Bearer " + tokens["admin"]}
    operator = {"Authorization": "Bearer " + tokens["operator"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        assert (await client.post("/ops/maintenance", headers=operator, json={"enabled": True})).status_code == 403
        assert (await client.post("/ops/maintenance", headers=admin, json={"enabled": "true"})).status_code == 422
        assert (await client.post("/ops/maintenance", headers=admin, json={"enabled": True})).status_code == 200
        assert DurableStore(store.path).maintenance()
        assert (await client.post("/scenarios", headers=operator, json={"prompt": "A box falls suddenly"})).status_code == 503
        assert (await client.post("/ops/maintenance", headers=admin, json={"enabled": False})).status_code == 200
        assert (await client.post("/scenarios", headers=operator, json={"prompt": "A box falls suddenly"})).status_code == 202


@pytest.mark.asyncio
async def test_concurrent_submissions_do_not_exceed_quota(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    monkeypatch.setattr(settings, "ghost_max_jobs_per_day", 3)
    monkeypatch.setattr(settings, "ghost_max_pending_jobs", 100)
    monkeypatch.setattr(store, "org_job_limits", (100, 100))
    headers = {"Authorization": "Bearer " + tokens["operator"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.post("/scenarios", headers=headers,
            json={"prompt": "A box falls suddenly", "seed": seed}) for seed in range(12)))
    assert sum(response.status_code == 202 for response in responses) == 3
    assert sum(response.status_code == 429 for response in responses) == 9
    assert store.job_counts()["submitted_today"] == 3


@pytest.mark.asyncio
async def test_concurrent_idempotent_submissions_create_one_job(private_api):
    app, _, store, tokens = private_api
    headers = {"Authorization": "Bearer " + tokens["operator"], "Idempotency-Key": "concurrent-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.post("/scenarios", headers=headers,
            json={"prompt": "A box falls suddenly", "seed": 42}) for _ in range(12)))
    assert all(response.status_code == 202 for response in responses)
    assert len({response.json()["trial"]["trial_id"] for response in responses}) == 1
    assert store.job_counts()["submitted_today"] == 1


@pytest.mark.asyncio
async def test_queue_restart_recovery_and_no_automatic_paid_retry(tmp_path):
    store = DurableStore(tmp_path / "state.sqlite3")
    pipeline = local_pipeline(store)
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A box falls suddenly"), persist=False)
    store.submit(scenario, trial, "persist-key", "hash")
    restored = DurableStore(store.path)
    await restored.load()
    assert restored.find_request("persist-key")["id"] == trial.trial_id
    runner = JobRunner(restored, local_pipeline(restored), Settings(_env_file=None))
    await runner.recover()
    assert restored.job(trial.trial_id)["state"] == "queued"
    runner.start()
    try:
        for _ in range(100):
            await asyncio.sleep(.01)
            if restored.trials[trial.trial_id].status == TrialStatus.DONE:
                break
    finally:
        await runner.stop()
    assert restored.trials[trial.trial_id].status == TrialStatus.DONE
    restored.trials[trial.trial_id].status = TrialStatus.SIMULATING
    await restored.put_trial(restored.trials[trial.trial_id])
    restored.job_state(trial.trial_id, "running")
    await runner.recover()
    assert restored.trials[trial.trial_id].status == TrialStatus.ERROR
    assert restored.job(trial.trial_id)["state"] == "error"


@pytest.mark.asyncio
async def test_job_timeout_closes_record_without_requeue(tmp_path):
    store = DurableStore(tmp_path / "jobs.sqlite3")
    pipeline = local_pipeline(store)
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A box falls suddenly"), persist=False)
    store.submit(scenario, trial)
    class SlowPipeline:
        async def run(self, trial_id):
            await asyncio.sleep(5)
    settings = Settings(_env_file=None, ghost_job_timeout_seconds=1)
    runner = JobRunner(store, SlowPipeline(), settings)
    runner.start()
    try:
        await asyncio.sleep(1.2)
    finally:
        await runner.stop()
    assert store.job(trial.trial_id)["state"] == "error"
    assert "remote compute" in store.trials[trial.trial_id].error


@pytest.mark.asyncio
async def test_backup_restore_and_exclusive_database_lease(tmp_path):
    store = DurableStore(tmp_path / "state.sqlite3")
    pipeline = local_pipeline(store)
    scenario, trial = await pipeline.create(ScenarioCreate(prompt="A box falls suddenly"))
    store.acquire_lease()
    try:
        with pytest.raises(RuntimeError, match="one Uvicorn"):
            DurableStore(store.path).acquire_lease()
    finally:
        store.release_lease()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "proof.json").write_text('{"example":true}')
    report = create_backup(store, artifacts, tmp_path / "backup.tgz")
    destination = tmp_path / "restore"
    assert restore_backup(tmp_path / "backup.tgz", destination, report["sha256"])["status"] == "restore_verified"
    restored = DurableStore(destination / "state.sqlite3")
    await restored.load()
    assert trial.trial_id in restored.trials
    assert (destination / "artifacts/proof.json").exists()
    with pytest.raises(ValueError, match="must not exist"):
        restore_backup(tmp_path / "backup.tgz", destination, report["sha256"])


def test_restore_rejects_path_traversal(tmp_path):
    archive_path = tmp_path / "bad.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("../escaped")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Unsafe"):
        restore_backup(archive_path, tmp_path / "restore", digest)
    assert not (tmp_path / "restore").exists()


def test_access_tokens_preserved_and_rotated_tokens_revoke_sessions(tmp_path):
    prepare_access(tmp_path / "private")
    original = (tmp_path / "private/access.env").read_bytes()
    prepare_access(tmp_path / "private")
    assert (tmp_path / "private/access.env").read_bytes() == original
    access = AccessControl(Settings(_env_file=None, ghost_admin_token="a" * 48, ghost_operator_token="o" * 48), None)
    session = access.session("operator")
    assert access.cookie_role(session) == "operator"
    assert access.cookie_role(session + "tampered") is None
    access.tokens["operator"] = "new" * 20
    assert access.cookie_role(session) is None


def test_production_rejects_missing_security_configuration():
    with pytest.raises(ValueError, match="GHOST_ADMIN_TOKEN"):
        AccessControl(Settings(_env_file=None, ghost_mode="production"), None)
    with pytest.raises(ValueError, match="GHOST_ALLOWED_ORIGINS"):
        AccessControl(Settings(_env_file=None, ghost_mode="production", ghost_admin_token="a" * 48), None)


def test_release_gate_never_accepts_empty_or_synthetic_runs(tmp_path):
    report = release_report([], {}, tmp_path, "sha256:expected", [])
    assert report["status"] == "blocked"
    assert report["certification"] is False
    assert len(report["failures"]) >= 4


def test_full_decode_rejects_signature_only_fixture(tmp_path):
    path = tmp_path / "fake.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypisom")
    with pytest.raises(ValueError, match="decode"):
        decode_video(path)


@pytest.mark.asyncio
async def test_one_workspace_cannot_exhaust_platform_quota(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    monkeypatch.setattr(settings, "ghost_max_pending_jobs", 100)
    monkeypatch.setattr(store, "org_job_limits", (100, 2))
    headers = {"Authorization": "Bearer " + tokens["operator"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        responses = [await client.post("/scenarios", headers=headers, json={"prompt": "A box falls suddenly", "seed": seed})
                     for seed in range(4)]
    assert [r.status_code for r in responses] == [202, 202, 429, 429]
    assert "daily trial allowance" in responses[-1].json()["detail"]


@pytest.mark.asyncio
async def test_logged_out_role_session_cookie_cannot_be_replayed(private_api):
    app, _, _, tokens = private_api
    origin = {"Origin": "https://console.test"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        await client.post("/auth/session", headers=origin, json={"token": tokens["operator"]})
        stolen = client.cookies.get("ghost_session")
        assert (await client.post("/auth/logout", headers=origin)).status_code == 200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test",
                                 cookies={"ghost_session": stolen}) as replay:
        assert (await replay.get("/trials")).status_code == 401


@pytest.mark.asyncio
async def test_unreadable_record_is_reported_not_fatal(tmp_path):
    store = DurableStore(tmp_path / "state.sqlite3")
    with store.connect() as db:
        db.execute("INSERT INTO records VALUES('trial','trl_bad','{\"not\": \"a trial\"}')")
        assert db.execute("PRAGMA user_version").fetchone()[0] >= 1
    await store.load()
    assert store.unreadable_records == [{"kind": "trial", "id": "trl_bad"}]


@pytest.mark.asyncio
async def test_cancel_refunds_unused_reservation(tmp_path):
    from ghost_trials.models import Scenario, StructuredDescription, Trial
    store = DurableStore(tmp_path / "state.sqlite3")
    with store.connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY,limit_cents INTEGER NOT NULL,used_cents INTEGER NOT NULL DEFAULT 0)")
        db.execute("INSERT INTO budgets VALUES('org_a',100,0)")
    scenario = Scenario(scenario_id="scn_r", prompt="A box falls suddenly", seed=1, severity_tag="medium", structured_description=StructuredDescription(
        objects=[], hazard_type="pending_generation", severity="medium", expected_safe_behavior="x"))
    trial = Trial(trial_id="trl_r", scenario_id="scn_r", organization_id="org_a")
    store.submit(scenario, trial, reservation_cents=30, platform_limit=100)
    assert store.cancel_queued("trl_r") and not store.cancel_queued("trl_r")
    with store.connect() as db:
        assert {r["id"]: r["used_cents"] for r in db.execute("SELECT * FROM budgets")} == {"platform": 0, "org_a": 0}


def test_client_address_respects_proxy_configuration():
    from types import SimpleNamespace
    from ghost_trials.security import AccessControl
    from ghost_trials.config import Settings
    request = lambda xff=None: SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"),
                                              headers={"x-forwarded-for": xff} if xff else {})
    access = AccessControl(Settings(_env_file=None), None)
    assert access.client_ip(request()) == "10.0.0.1"
    # Behind an unconfigured proxy every client would share the proxy's address: no per-client bucket.
    assert access.client_ip(request("198.51.100.7, 203.0.113.2")) is None
    access.settings = Settings(_env_file=None, ghost_trusted_proxy_hops=2)
    assert access.client_ip(request("198.51.100.7, 203.0.113.2")) == "198.51.100.7"
    assert access.client_ip(request("192.0.2.9, 198.51.100.7, 203.0.113.2")) == "198.51.100.7"


@pytest.mark.asyncio
async def test_oversized_hunt_is_rejected_before_it_starts(private_api, monkeypatch):
    app, settings, store, tokens = private_api
    monkeypatch.setattr(settings, "ghost_max_org_jobs_per_day", 5)
    headers = {"Authorization": "Bearer " + tokens["operator"]}
    body = {"objective": {"task": "position a block with gantry arm", "environment": "CPU MuJoCo tabletop",
                          "hazard_type": "object_positioning"}, "max_trials": 6, "strategy": "adaptive"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/hunts", headers=headers, json=body)
    assert response.status_code == 429 and "more trials today" in response.json()["detail"]


def test_role_cookie_without_jti_is_rejected():
    import base64, hashlib, hmac, json as _json, time as _time
    from ghost_trials.config import Settings
    from ghost_trials.security import AccessControl
    access = AccessControl(Settings(_env_file=None, ghost_admin_token="a" * 48), None)
    payload = base64.urlsafe_b64encode(_json.dumps({"role": "admin", "exp": int(_time.time()) + 60,
        "version": hashlib.sha256(("a" * 48).encode()).hexdigest()}).encode()).decode()
    legacy = payload + "." + hmac.new(("a" * 48).encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert access.cookie_role(legacy) is None
    assert access.cookie_role(access.session("admin")) == "admin"
