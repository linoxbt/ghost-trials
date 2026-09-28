import httpx
import pytest

from ghost_trials.monitor import check


@pytest.mark.asyncio
async def test_private_monitor_reports_unhealthy_runner_and_failed_jobs():
    def handler(request):
        assert request.url.path == "/ops/status"
        assert request.headers["authorization"] == "Bearer monitor-secret"
        return httpx.Response(200, json={"database_ok": True, "runner_alive": False,
                                        "jobs": {"states": {"error": 2}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        faults = await check(client, "https://private-api.test", "monitor-secret")
    assert faults == ["API database or job runner unhealthy", "Recorded failed jobs: 2"]
