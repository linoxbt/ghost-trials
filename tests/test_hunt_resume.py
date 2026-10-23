"""Resume after a restart: interrupted free CPU work re-runs, a changed controller is refused, no double launch."""
import asyncio

import httpx
import pytest

from ghost_trials.app import app, hunt_service, settings, store
from ghost_trials.cpu_robot import controller
from ghost_trials.hunt import Hunt, HuntObjective, HuntStatus, PolicyVersion, TrialCandidate, default_space
from ghost_trials.models import Trial, TrialStatus


@pytest.fixture
def interrupted_cpu_hunt(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "path", tmp_path / "resume.sqlite3")
    monkeypatch.setattr(store, "trials", {})
    monkeypatch.setattr(store, "scenarios", {})
    monkeypatch.setattr(settings, "ghost_simulator_provider", "mujoco_cpu")
    launches = []
    monkeypatch.setattr(hunt_service, "launch", lambda hunt_id, subject: launches.append(hunt_id))
    selected = controller("gantry-push-v1")
    hunt = Hunt(hunt_id="hunt_resume", organization_id="legacy",
                objective=HuntObjective(task="position a block with gantry arm", hazard_type="object_positioning",
                                        environment="CPU MuJoCo tabletop"),
                policy=PolicyVersion(name=selected.name, checkpoint="builtin:test", checkpoint_digest=selected.digest,
                                     embodiment="GANTRY_PUSH_CPU"),
                search_space=default_space("object_positioning", "mujoco_cpu"), max_trials=4,
                status=HuntStatus.BLOCKED)
    hunt.candidates.append(TrialCandidate(sequence=1, phase="explore", controls={}, seed=7, trial_id="trl_cut"))
    store.trials["trl_cut"] = Trial(trial_id="trl_cut", scenario_id="scn_cut", organization_id="legacy",
        status=TrialStatus.ERROR, error="Interrupted execution; remote compute may still be active. Review worker before replaying.")
    hunt_service.save(hunt)
    return hunt, launches


@pytest.mark.asyncio
async def test_resume_reruns_the_interrupted_cpu_trial(interrupted_cpu_hunt):
    hunt, launches = interrupted_cpu_hunt
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post(f"/hunts/{hunt.hunt_id}/resume")
    assert response.status_code == 202, response.text
    saved = hunt_service.get(hunt.hunt_id)
    assert saved.candidates[0].attempt == 1 and saved.candidates[0].trial_id is None
    assert launches == [hunt.hunt_id]


@pytest.mark.asyncio
async def test_resume_refuses_a_changed_controller(interrupted_cpu_hunt):
    hunt, launches = interrupted_cpu_hunt
    hunt.policy.checkpoint_digest = "sha256:" + "0" * 64
    hunt_service.save(hunt)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post(f"/hunts/{hunt.hunt_id}/resume")
    assert response.status_code == 409 and "checkpoint changed" in response.json()["detail"]
    assert launches == []


@pytest.mark.asyncio
async def test_simultaneous_resumes_launch_once(interrupted_cpu_hunt, monkeypatch):
    hunt, launches = interrupted_cpu_hunt
    running = asyncio.get_running_loop().create_future()

    def launch(hunt_id, subject):
        launches.append(hunt_id)
        hunt_service.tasks[hunt_id] = running  # still running for the second request

    monkeypatch.setattr(hunt_service, "launch", launch)
    monkeypatch.setattr(hunt_service, "tasks", {})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.post(f"/hunts/{hunt.hunt_id}/resume") for _ in range(2)))
    running.cancel()
    assert sorted(r.status_code for r in responses) == [202, 409]
    assert launches == [hunt.hunt_id]
