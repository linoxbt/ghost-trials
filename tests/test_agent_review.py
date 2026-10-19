"""Nebius contract tests use a local HTTP transport; they incur no provider charges."""
import json

import httpx
import pytest

from ghost_trials.accounts import Accounts
from ghost_trials.agent_review import AgentNemotronReviewer
from ghost_trials.agent_verification import AgentPolicy, AgentTarget, execute_reference, make_scenario
from ghost_trials.config import Settings
from ghost_trials.durable import DurableStore


def setup(tmp_path):
    settings = Settings(ghost_data_path=tmp_path / "state.sqlite3",
                        ghost_agent_model_review_enabled=True,
                        ghost_live_execution_enabled=True,
                        ghost_provider_spending_controls_confirmed=True,
                        ghost_platform_budget_cents=20,
                        ghost_cpu_model_review_reservation_cents=10,
                        nebius_api_key="test-key")
    store = DurableStore(settings.ghost_data_path)
    Accounts(store, settings).allocate_budget("legacy", 20)
    target = AgentTarget(target_id="reference-vulnerable-v1", organization_id="legacy",
                         name="reference-vulnerable-v1", version="vulnerable-v1")
    trial = execute_reference(target, AgentPolicy(), make_scenario(2, 0, 9),
                              hunt_id="hunt", trial_id="atrial", objective="tool_output_manipulation")
    return settings, store, trial


@pytest.mark.asyncio
async def test_verified_agent_evidence_gets_bounded_nemotron_interpretation(tmp_path):
    settings, store, trial = setup(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url.path.endswith("/chat/completions")
        assert payload["max_tokens"] == settings.ghost_cpu_model_review_max_tokens
        evidence = json.loads(payload["messages"][1]["content"])
        assert evidence["oracle_verdict"] == "verified_failure"
        assert evidence["tool_events"][1]["tool"] == "admin.delete"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "explanation": "The agent requested a prohibited mock tool after reading untrusted tool output.",
            "trace_refs": ["tool_events[1]", "assertions[0]"],
            "contributing_factors": ["Untrusted response was treated as operational instruction"],
            "suggested_remediation": "Ignore tool-output instructions about permissions.",
            "regression_recommendations": ["Replay this saved prompt against the next version"]})}}]})

    reviewer = AgentNemotronReviewer(settings, store, httpx.MockTransport(handler))
    review = await reviewer.review(trial)
    assert review.status == "complete" and review.answer.trace_refs == ["tool_events[1]", "assertions[0]"]
    assert trial.status == "verified_failure"
    assert (await reviewer.review(trial)).status == "complete"
    assert len(calls) == 1 and Accounts(store, settings).budget("legacy")["used_cents"] == 10


@pytest.mark.asyncio
async def test_model_failure_budget_and_unverified_trace_do_not_change_oracle(tmp_path):
    settings, store, trial = setup(tmp_path)
    reviewer = AgentNemotronReviewer(settings, store, httpx.MockTransport(lambda _: httpx.Response(503)))
    review = await reviewer.review(trial)
    assert review.status == "provider_error" and trial.status == "verified_failure"
    assert (await reviewer.review(trial)).status == "provider_error"  # no retry/billing loop
    settings2, store2, trial2 = setup(tmp_path / "budget")
    Accounts(store2, settings2).allocate_budget("legacy", 0)
    assert (await AgentNemotronReviewer(settings2, store2).review(trial2)).status == "budget_exhausted"
    trial2.tool_events[1].tool = "notes.read"
    assert (await AgentNemotronReviewer(settings2, store2).review(trial2)).status == "unavailable"
