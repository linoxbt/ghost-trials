from ghost_trials.config import Settings
from ghost_trials.live_hunt_preflight import inspect


def test_preflight_blocks_unconfigured_paid_hunt_without_exposing_secrets():
    report = inspect(Settings(_env_file=None, cosmos_api_style="nvidia_catalog",
                              nvidia_api_key=None, cosmos_api_key=None,
                              ghost_live_execution_enabled=False,
                              ghost_provider_spending_controls_confirmed=False), 3)
    assert report["ready_to_attempt_live_hunt"] is False
    assert report["external_provider_cap_independently_verified"] is False
    assert report["robot_trial_executed"] is False
    assert "NVIDIA_API_KEY" in " ".join(report["missing_or_unconfirmed"])


def test_preflight_requires_budget_for_entire_bounded_hunt():
    settings = Settings(_env_file=None, ghost_mode="production", ghost_scenario_provider="cosmos",
                        ghost_simulator_provider="isaac_http", ghost_judge_provider="nebius",
                        cosmos_api_style="nvidia_catalog", nvidia_api_key="test-key",
                        nebius_api_key="test-key", isaac_job_endpoint="https://worker.example",
                        isaac_job_token="test-token", gr00t_checkpoint="/models/g1",
                        gr00t_checkpoint_digest="sha256:test", ghost_customer_auth_required=True,
                        ghost_provider_spending_controls_confirmed=True,
                        ghost_live_execution_enabled=True, ghost_live_job_reservation_cents=50,
                        ghost_platform_budget_cents=100, cosmos_num_frames=25)
    report = inspect(settings, 3)
    assert report["maximum_admission_reservation_cents"] == 150
    assert not report["ready_to_attempt_live_hunt"]
    settings.ghost_platform_budget_cents = 150
    assert inspect(settings, 3)["ready_to_attempt_live_hunt"]
