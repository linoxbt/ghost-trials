"""These tests execute the bundled agent process; no success response is mocked."""
import asyncio
import json

import httpx
import pytest

from ghost_trials.agent_verification import (AgentGhostCase, AgentPolicy, AgentTarget, AgentVerdict, TARGETS,
                                              execute_reference, make_scenario, verify_trial)
from ghost_trials.app import app, lifespan, store, settings, access
from ghost_trials.accounts import Principal


def target(name="reference-vulnerable-v1", org="org-a"):
    return AgentTarget(target_id=name, organization_id=org, name=name, version=TARGETS[name])


def test_real_reference_execution_and_oracle():
    policy = AgentPolicy()
    benign = execute_reference(target(), policy, make_scenario(0, 0, 7),
                               hunt_id="h", trial_id="t0", objective="task_completion")
    attacked = execute_reference(target(), policy, make_scenario(2, 0, 7),
                                 hunt_id="h", trial_id="t1", objective="tool_output_manipulation")
    corrected = execute_reference(target("reference-corrected-v2"), policy, make_scenario(2, 0, 7),
                                  hunt_id="h", trial_id="t2", objective="tool_output_manipulation")
    assert benign.status == AgentVerdict.VERIFIED_SUCCESS
    assert attacked.status == AgentVerdict.VERIFIED_FAILURE
    assert corrected.status == AgentVerdict.VERIFIED_SUCCESS
    assert attacked.tool_events[1].tool == "admin.delete" and not attacked.tool_events[1].executed
    assert attacked.assertions[0].evidence_ref == "tool_events[1]"
    assert all(verify_trial(t) for t in (benign, attacked, corrected))
    attacked.tool_events[1].tool = "notes.read"
    assert not verify_trial(attacked)


def test_hanging_agent_is_execution_error_not_failure():
    trial = execute_reference(target("reference-hang-v1"), AgentPolicy(), make_scenario(0, 0, 1),
                              hunt_id="h", trial_id="t", objective="task_completion", timeout_s=.2)
    assert trial.status == AgentVerdict.EXECUTION_ERROR
    assert trial.assertions == [] and "TimeoutError" in trial.error
    assert verify_trial(trial)


@pytest.mark.asyncio
async def test_agent_hunt_replay_regression_and_persistence(tmp_path):
    store.path = tmp_path / "agent-hunt.json"
    store.scenarios.clear()
    store.trials.clear()
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            request = {"domain": "ai_agent", "target_id": "reference-vulnerable-v1",
                       "objective": {"verification_objective": "tool_output_manipulation"},
                       "max_trials": 6, "strategy": "adaptive"}
            response = await client.post("/hunts", json=request)
            assert response.status_code == 202, response.text
            hunt_id = response.json()["hunt_id"]
            for _ in range(100):
                hunt = (await client.get(f"/hunts/{hunt_id}")).json()
                if hunt["status"] in {"complete", "blocked"}:
                    break
                await asyncio.sleep(.1)
            assert hunt["status"] == "complete", hunt
            assert len(hunt["candidates"]) == 6
            assert hunt["case_ids"]
            assert any(c["phase"] == "reproduce" for c in hunt["candidates"])
            case_id = hunt["case_ids"][0]
            case = (await client.get(f"/ghost-cases/{case_id}")).json()
            assert case["domain"] == "ai_agent"
            assert case["reproduction_status"] == "reproducible"
            assert case["scenario"]["attack_variant"] == 2
            baseline_id = case["baseline_trial_id"]
            evidence = (await client.get(f"/agent-trials/{baseline_id}")).json()
            assert evidence["evidence_verified"] and evidence["status"] == "verified_failure"
            assert (await client.get(f"/agent-trials/{baseline_id}/model-review")).json()["status"] == "not_requested"
            assert (await client.post(f"/agent-trials/{baseline_id}/model-review")).json()["status"] == "disabled"
            replay = await client.post(f"/agent-trials/{baseline_id}/replay")
            assert replay.status_code == 200, replay.text
            assert replay.json()["same_verdict"] and replay.json()["evidence_verified"]
            assert replay.json()["exact_trace_match"]
            regression = await client.post(f"/ghost-cases/{case_id}/regressions",
                                           json={"target_id": "reference-corrected-v2"})
            assert regression.status_code == 202, regression.text
            assert regression.json()["outcome"] == "fixed_on_case"
            assert (await client.get(f"/ghost-cases/{case_id}/regressions")).json()[0]["outcome"] == "fixed_on_case"
            assert (await client.get("/agent-targets")).status_code == 200
            assert (await client.post("/hunts", json={**request, "target_id": "arbitrary-command"})).status_code == 422
            # A new service instance reads the same durable Hunt and case records.
            from ghost_trials.hunt_runtime import HuntService
            from ghost_trials.app import pipeline, settings, submission_allowed, submission_lock
            reloaded = HuntService(store, pipeline, settings, submission_allowed, submission_lock)
            assert reloaded.get(hunt_id).case_ids == hunt["case_ids"]
            assert reloaded.case(case_id).scenario.seed == case["scenario"]["seed"]
            evidence["tool_events"][1]["tool"] = "notes.read"
            evidence.pop("evidence_verified")
            store.put_domain("agent_trial", baseline_id, json.dumps(evidence))
            assert (await client.get(f"/agent-trials/{baseline_id}")).json()["evidence_verified"] is False
            assert (await client.get(f"/ghost-cases/{case_id}")).json()["evidence_verification"]["status"] == "invalid"
            assert (await client.get(f"/ghost-cases/{case_id}/regressions")).json()[0]["outcome"] == "incompatible_or_unverified"


@pytest.mark.asyncio
async def test_agent_records_are_tenant_scoped(tmp_path, monkeypatch):
    store.path = tmp_path / "agent-tenants.json"
    store.scenarios.clear()
    store.trials.clear()
    trial = execute_reference(target(org="org-a"), AgentPolicy(), make_scenario(2, 0, 2),
                              hunt_id="hunt_a", trial_id="atrial_a", objective="tool_output_manipulation")
    store.put_domain("agent_trial", trial.trial_id, trial.model_dump_json())
    case = AgentGhostCase(case_id="gcase_a", hunt_id="hunt_a", organization_id="org-a",
                          baseline_trial_id=trial.trial_id, target=trial.target, policy=trial.policy,
                          objective=trial.objective, scenario=trial.scenario,
                          assertion_ids=["forbidden_tool_invocation"], evidence_sha256=trial.evidence_sha256)
    store.put_domain("ghost_case", case.case_id, case.model_dump_json())
    monkeypatch.setattr(access, "principal", lambda request: Principal("subject-b", "org-b", "viewer", "demo"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/agent-trials/atrial_a")).status_code == 404
        assert (await client.get("/ghost-cases/gcase_a")).status_code == 404
        assert (await client.get("/ghost-cases")).json() == []


@pytest.mark.asyncio
async def test_agent_hunt_daily_budget_and_provider_failure_are_not_policy_failures(tmp_path, monkeypatch):
    store.path = tmp_path / "agent-budget.json"
    store.scenarios.clear()
    store.trials.clear()
    monkeypatch.setattr(settings, "ghost_max_jobs_per_day", 1)
    async with lifespan(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/hunts", json={"domain": "ai_agent",
                "objective": {"verification_objective": "tool_output_manipulation"}, "max_trials": 3})
            assert response.status_code == 202
            for _ in range(60):
                hunt = (await client.get(f"/hunts/{response.json()['hunt_id']}")).json()
                if hunt["status"] == "blocked":
                    break
                await asyncio.sleep(.1)
            assert hunt["status"] == "blocked"
            assert len(hunt["candidates"]) <= 2
            assert hunt["case_ids"] == []
            assert (await client.get("/ghost-cases")).json() == []
            assert len(store.list_domain("agent_reservation")) == 1
    # The timeout target returns an execution error with no oracle failure.
    timed = execute_reference(target("reference-hang-v1"), AgentPolicy(), make_scenario(0, 0, 1),
                              hunt_id="h", trial_id="timeout", objective="task_completion", timeout_s=.2)
    assert timed.status == AgentVerdict.EXECUTION_ERROR and not timed.assertions


def test_legacy_physical_models_default_to_original_domain():
    from ghost_trials.hunt import Hunt, GhostCase
    assert Hunt.model_fields["domain"].default == "physical_ai"
    assert GhostCase.model_fields["domain"].default == "physical_ai"
