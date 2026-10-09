import asyncio

import httpx
import pytest

from ghost_trials.app import app, lifespan, pipeline, store


@pytest.mark.asyncio
async def test_local_hunt_vertical_slice_is_explicitly_synthetic(tmp_path):
    store.path = tmp_path / "hunt-api.json"
    store.scenarios.clear()
    store.trials.clear()
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/hunts", json={"objective": {
                "task": "walk forward 1m", "environment": "configured SONIC MuJoCo scene",
                "hazard_type": "surface_instability"}, "max_trials": 3})
            assert response.status_code == 202, response.text
            hunt_id = response.json()["hunt_id"]
            for _ in range(90):
                state = (await client.get(f"/hunts/{hunt_id}")).json()
                if state["status"] in {"complete", "blocked"}:
                    break
                await asyncio.sleep(.1)
            assert state["status"] == "complete", state
            assert len(state["candidates"]) == 3
            assert state["trials_executed"] == 3 and state["failures_discovered"] == 0
            assert all(c["evidence_class"] == "synthetic_demo" for c in state["candidates"])
            assert all(c["trial_id"] for c in state["candidates"])
            assert (await client.get("/ghost-cases")).json() == []
            trial = (await client.get(f"/trials/{state['candidates'][0]['trial_id']}")).json()
            assert trial["scenario"]["execution_recipe"]["kind"] == "surface_instability"
            unsupported = await client.post("/hunts", json={"objective": {
                "task": "Run arbitrary user task", "environment": "unconfigured warehouse",
                "hazard_type": "falling_object"}, "max_trials": 3})
            assert unsupported.status_code == 422


@pytest.mark.asyncio
async def test_hunt_blocks_generated_hazard_mismatch_without_robot_verdict(tmp_path, monkeypatch):
    store.path = tmp_path / "hunt-mismatch.json"
    store.scenarios.clear()
    store.trials.clear()
    original = pipeline.generator.generate

    async def mismatched(*args, **kwargs):
        scenario = await original(*args, **kwargs)
        scenario.structured_description.hazard_type = "falling_object"
        return scenario

    monkeypatch.setattr(pipeline.generator, "generate", mismatched)
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/hunts", json={"objective": {
                "task": "walk forward 1m", "environment": "configured SONIC MuJoCo scene",
                "hazard_type": "surface_instability"}, "max_trials": 3})
            assert response.status_code == 202
            hunt_id = response.json()["hunt_id"]
            for _ in range(90):
                state = (await client.get(f"/hunts/{hunt_id}")).json()
                if state["status"] == "blocked":
                    break
                await asyncio.sleep(.1)
            assert state["status"] == "blocked"
            assert state["failures_discovered"] == 0
            trial_id = state["candidates"][0]["trial_id"]
            trial = (await client.get(f"/trials/{trial_id}")).json()
            assert trial["metrics"] is None and trial["score_category"] is None
