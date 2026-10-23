"""Private health polling and deduplicated webhook alerts; no paid model calls."""
import asyncio
import json
import os
import shutil
import time

import httpx


async def check(client, origin, token):
    response = await client.get(origin.rstrip("/") + "/ops/status", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    status = response.json()
    faults = []
    if not status["database_ok"] or not status["runner_alive"]:
        faults.append("API database or job runner unhealthy")
    # The all-time error count never decreases, so alert only on recent failures; one old failure
    # must not keep the monitor in a permanent alert state.
    jobs = status["jobs"]
    recent = jobs["errors_last_hour"] if "errors_last_hour" in jobs else jobs["states"].get("error", 0)
    if recent:
        faults.append(f"Failed jobs in the last hour: {recent}")
    return faults


async def main_async():
    origin = os.environ.get("GHOST_MONITOR_ORIGIN", "http://dashboard:8000")
    token = os.environ["GHOST_ADMIN_TOKEN"]
    webhook = os.environ.get("GHOST_ALERT_WEBHOOK")
    previous = None
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        while True:
            try:
                faults = await check(client, origin, token)
            except (httpx.HTTPError, ValueError, KeyError):
                faults = ["API monitoring check failed"]
            disk = shutil.disk_usage(os.environ.get("GHOST_MONITOR_DISK", "/data"))
            if disk.free < 1_000_000_000:
                faults.append("Less than 1 GB free on evidence volume")
            fingerprint = tuple(faults)
            if fingerprint != previous:
                event = {"at": int(time.time()), "service": "ghost-trials", "status": "alert" if faults else "healthy", "issues": faults}
                print(json.dumps(event), flush=True)
                if webhook:
                    try:
                        response = await client.post(webhook, json=event)
                        response.raise_for_status()
                    except httpx.HTTPError:
                        print(json.dumps({"status": "alert_delivery_failed"}), flush=True)
                        await asyncio.sleep(30)
                        continue
                previous = fingerprint
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main_async())
