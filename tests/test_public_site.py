import httpx
import pytest

from ghost_trials.app import app, settings


@pytest.mark.asyncio
async def test_public_docs_workspace_and_api_have_distinct_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for path, marker in [
            ("/", "Release the Ghost"), ("/app/", "hunt.js"),
            ("/docs", "Ghost Hunt"), ("/api/docs", "swagger-ui"),
        ]:
            response = await client.get(path)
            assert response.status_code == 200
            assert marker in response.text


@pytest.mark.asyncio
async def test_capabilities_report_absent_generation_without_exposing_secrets(monkeypatch):
    for key in ["cosmos_base_url", "scenario_reasoner_api_key", "nebius_api_key", "isaac_job_endpoint", "isaac_job_token", "gr00t_checkpoint", "gr00t_checkpoint_digest"]:
        monkeypatch.setattr(settings, key, None)
    monkeypatch.setattr(settings, "ghost_scenario_provider", "local")
    monkeypatch.setattr(settings, "ghost_simulator_provider", "local")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/capabilities")).json()
        assert data["video_generation_enabled"] is False
        assert data["robot_execution_enabled"] is False
        assert "Cosmos endpoint" in data["missing_configuration"]
        assert data["readiness"] == "not_configured"
        monkeypatch.setattr(settings, "isaac_job_token", "never-return-this-token")
        response = await client.get("/capabilities")
        assert "never-return-this-token" not in response.text
        assert "GPU worker token" not in response.json()["missing_configuration"]
