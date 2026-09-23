import base64
import json

import httpx
import pytest

from ghost_trials.config import Settings
from ghost_trials.models import Scenario, Severity, StructuredDescription
from ghost_trials.production import (
    CosmosVideoClient,
    IsaacRemoteSimulator,
    OpenAICompatibleScenarioReasoner,
    ProductionConfigurationError,
)
from workers.isaac.trial_runner import derive_metrics


MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom"


@pytest.mark.asyncio
async def test_cosmos_nim_contract_decodes_and_validates_mp4():
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/infer"
        payload = json.loads(request.content)
        assert payload["num_output_frames"] == 121
        return httpx.Response(200, json={"b64_video": base64.b64encode(MP4).decode()})

    settings = Settings(cosmos_base_url="http://cosmos/", cosmos_api_style="nim")
    client = CosmosVideoClient(settings, transport=httpx.MockTransport(handler))
    assert await client.generate("A safe warehouse trial", 42) == MP4


@pytest.mark.asyncio
async def test_cosmos_vllm_contract_uses_multipart_and_returns_mp4():
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/videos/sync"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b'name="num_frames"' in request.content
        assert b"121" in request.content
        return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})

    settings = Settings(cosmos_base_url="http://cosmos/", cosmos_api_style="vllm")
    client = CosmosVideoClient(settings, transport=httpx.MockTransport(handler))
    assert await client.generate("A safe warehouse trial", 42) == MP4


def test_cosmos_rejects_invalid_frame_cadence():
    with pytest.raises(ProductionConfigurationError, match="4k\\+1"):
        CosmosVideoClient(Settings(cosmos_base_url="http://cosmos/", cosmos_num_frames=120))


@pytest.mark.asyncio
async def test_structured_reasoner_uses_openai_compatible_contract():
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({
                    "objects": ["robot", "box"],
                    "hazard_type": "falling_object",
                    "severity": "high",
                    "expected_safe_behavior": "React within 350 ms and retain 0.65 m clearance.",
                })}}]
            },
        )

    settings = Settings(
        scenario_reasoner_api_key="test",
        scenario_reasoner_base_url="http://reasoner/v1/",
    )
    reasoner = OpenAICompatibleScenarioReasoner(settings, httpx.MockTransport(handler))
    result = await reasoner.expand("A box falls", Severity.HIGH)
    assert result.hazard_type == "falling_object"
    assert result.severity == Severity.HIGH


@pytest.mark.asyncio
async def test_isaac_worker_job_contract_requires_artifacts():
    polls = 0

    def handler(request: httpx.Request):
        nonlocal polls
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "isaac_1"})
        polls += 1
        return httpx.Response(200, json={
            "status": "completed",
            "result": {"metrics": {
                "time_to_react_ms": 330,
                "min_clearance_m": 0.7,
                "task_completed": True,
                "fall_or_collision": False,
                "simulation_video_url": "https://worker/video.mp4",
                "trace_url": "https://worker/trace.jsonl",
            }},
        })

    settings = Settings(
        isaac_job_endpoint="http://worker/",
        gr00t_checkpoint="/models/checkpoint",
        isaac_poll_interval_seconds=0,
    )
    simulator = IsaacRemoteSimulator(settings, httpx.MockTransport(handler))
    scenario = Scenario(
        scenario_id="scn_1",
        prompt="A box falls",
        structured_description=StructuredDescription(
            objects=["robot", "box"],
            hazard_type="falling_object",
            severity=Severity.HIGH,
            expected_safe_behavior="React within 350 ms and retain 0.65 m clearance.",
        ),
        severity_tag=Severity.HIGH,
        seed=42,
    )
    metrics = await simulator.run(scenario)
    assert metrics.time_to_react_ms == 330
    assert polls == 1


def test_trace_metric_derivation_is_evidence_based(tmp_path):
    trace = tmp_path / "telemetry.jsonl"
    trace.write_text("\n".join(json.dumps(row) for row in [
        {"timestamp_ms": 1000, "hazard_active": True, "clearance_m": 0.8, "collision": False, "fall": False, "policy_reacted": False, "simulator_version": "Isaac Sim 6"},
        {"timestamp_ms": 1320, "hazard_active": True, "clearance_m": 0.55, "collision": False, "fall": False, "policy_reacted": True, "task_completed": True},
    ]))
    metrics = derive_metrics(trace, {"policy": {"checkpoint_digest": "sha256:abc"}})
    assert metrics.time_to_react_ms == 320
    assert metrics.min_clearance_m == 0.55
    assert metrics.policy_checkpoint_digest == "sha256:abc"
