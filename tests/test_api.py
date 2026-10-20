import asyncio

import httpx
import pytest

from ghost_trials.app import app, lifespan, store


@pytest.mark.asyncio
async def test_public_health_fails_if_worker_is_not_running(monkeypatch):
    from ghost_trials.app import runner
    monkeypatch.setattr(runner, "task", None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_api_accepts_and_completes_trial(tmp_path):
    store.path = tmp_path / "api-state.json"
    store.scenarios.clear()
    store.trials.clear()

    transport = httpx.ASGITransport(app=app)
    async with lifespan(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert (await client.get("/assets/app.css")).status_code == 200
            assert (await client.get("/assets/app.js")).status_code == 200
            assert (await client.get("/assets/production.css")).status_code == 200
            preview = await client.get(f"/artifacts/{next(iter(store.scenarios))}/preview")
            assert preview.headers["x-frame-options"] == "SAMEORIGIN"

            response = await client.post(
                "/scenarios",
                json={
                    "prompt": "A forklift reverses unexpectedly beside the robot",
                    "severity": "high",
                    "seed": 99,
                },
            )
            assert response.status_code == 202
            trial_id = response.json()["trial"]["trial_id"]

            for _ in range(30):
                detail = await client.get(f"/trials/{trial_id}")
                if detail.json()["status"] == "done":
                    break
                await asyncio.sleep(0.05)

            assert detail.json()["status"] == "done"
            assert detail.json()["metrics"]["time_to_react_ms"] > 0
            summary = (await client.get("/safety-score")).json()
            assert summary["n_trials"] == 7
            assert summary["score_available"] is False
            assert summary["safety_score"] is None
            assert summary["scored_trials"] == 0
            assert summary["excluded_trials"] == 7


@pytest.mark.asyncio
async def test_api_rejects_short_prompt(tmp_path):
    store.path = tmp_path / "empty-state.json"
    store.scenarios.clear()
    store.trials.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/scenarios", json={"prompt": "box"})
    assert response.status_code == 422
