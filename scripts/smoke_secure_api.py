"""Network-free container smoke: auth, queue execution and concurrent reads."""
import asyncio
import os
import secrets

import httpx


async def main():
    token = secrets.token_urlsafe(48)
    os.environ.update(GHOST_MODE="local", GHOST_ADMIN_TOKEN=token,
                     GHOST_PIPELINE_DELAY_SECONDS="0", GHOST_DATA_PATH="/data/smoke.sqlite3")
    from ghost_trials.app import app, lifespan
    async with lifespan(app), httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://smoke") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/trials")).status_code == 401
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "smoke-trial"}
        accepted = await client.post("/scenarios", json={"prompt": "A heavy box falls from a shelf", "seed": 42}, headers=headers)
        assert accepted.status_code == 202
        trial_id = accepted.json()["trial"]["trial_id"]
        for _ in range(100):
            detail = await client.get(f"/trials/{trial_id}", headers=headers)
            if detail.json()["status"] == "done":
                break
            await asyncio.sleep(.02)
        assert detail.json()["status"] == "done"
        results = await asyncio.gather(*(client.get("/trials", headers=headers) for _ in range(30)))
        assert all(response.status_code == 200 for response in results)
        assert (await client.get("/ready", headers=headers)).status_code == 200
        status = (await client.get("/ops/status", headers=headers)).json()
        assert status["database_ok"] and status["runner_alive"]
        print("Secure container smoke passed: authentication, durable job, evidence API and 30 concurrent reads; synthetic execution only.")


if __name__ == "__main__":
    asyncio.run(main())
