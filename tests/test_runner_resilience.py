import asyncio
from types import SimpleNamespace

import pytest

from ghost_trials.jobs import JobRunner
from ghost_trials.models import Trial, TrialStatus


class FakeStore:
    def __init__(self, ids):
        self.queue = list(ids)
        self.trials = {i: Trial(trial_id=i, scenario_id="scn_x") for i in ids}
        self.states = {}

    def claim(self):
        return self.queue.pop(0) if self.queue else None

    async def put_trial(self, trial):
        self.trials[trial.trial_id] = trial

    def job_state(self, trial_id, state):
        self.states[trial_id] = state

    def audit(self, *args, **kwargs):
        pass


class FlakyPipeline:
    def __init__(self, store):
        self.store, self.ran = store, []

    async def run(self, trial_id):
        self.ran.append(trial_id)
        if trial_id == "trl_bad":
            raise KeyError("scenario missing")
        self.store.trials[trial_id].status = TrialStatus.DONE


@pytest.mark.asyncio
async def test_runner_survives_unexpected_job_error():
    store = FakeStore(["trl_bad", "trl_good"])
    pipeline = FlakyPipeline(store)
    runner = JobRunner(store, pipeline, SimpleNamespace(ghost_job_timeout_seconds=5))
    runner.start()
    for _ in range(100):
        if store.states.get("trl_good"):
            break
        await asyncio.sleep(.02)
    await runner.stop()
    assert pipeline.ran == ["trl_bad", "trl_good"]
    assert store.states == {"trl_bad": "error", "trl_good": "done"}
    assert store.trials["trl_bad"].status == TrialStatus.ERROR


@pytest.mark.asyncio
async def test_publish_tolerates_subscriber_changes_mid_broadcast(monkeypatch):
    from ghost_trials import app as app_module
    from ghost_trials.models import LiveEvent

    class Socket:
        def __init__(self, join=None):
            self.state = SimpleNamespace(principal=SimpleNamespace(organization_id="org_a"))
            self.join, self.sent = join, 0

        async def send_json(self, payload):
            self.sent += 1
            if self.join:
                app_module.subscribers.add(self.join)

    late = Socket()
    first = Socket(join=late)
    monkeypatch.setattr(app_module, "subscribers", {first})
    monkeypatch.setattr(app_module.access, "principal", lambda socket: socket.state.principal)
    trial = SimpleNamespace(organization_id="org_a")
    monkeypatch.setattr(app_module.store, "trials", {"trl_live": trial})
    await app_module.publish(LiveEvent(trial_id="trl_live", status=TrialStatus.DONE, message="done"))
    assert first.sent == 1 and first in app_module.subscribers


@pytest.mark.asyncio
async def test_a_stuck_socket_cannot_stall_the_broadcast(monkeypatch):
    import time as _time
    from ghost_trials import app as app_module
    from ghost_trials.models import LiveEvent

    class Socket:
        def __init__(self, delay):
            self.state = SimpleNamespace(principal=SimpleNamespace(organization_id="org_a"))
            self.delay, self.sent = delay, 0

        async def send_json(self, payload):
            await asyncio.sleep(self.delay)
            self.sent += 1

    sockets = [Socket(60) for _ in range(5)] + [Socket(0)]
    monkeypatch.setattr(app_module, "subscribers", set(sockets))
    monkeypatch.setattr(app_module.access, "principal", lambda socket: socket.state.principal)
    monkeypatch.setattr(app_module.store, "trials", {"trl_live": SimpleNamespace(organization_id="org_a")})
    started = _time.monotonic()
    await app_module.publish(LiveEvent(trial_id="trl_live", status=TrialStatus.DONE, message="done"))
    assert _time.monotonic() - started < 3.5
    assert sockets[-1].sent == 1 and app_module.subscribers == {sockets[-1]}
