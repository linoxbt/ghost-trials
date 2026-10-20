from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ghost_mode: str = "cpu"
    ghost_data_path: Path = Path("data/state.json")
    ghost_artifact_root: Path = Path("artifacts/generated")
    ghost_pipeline_delay_seconds: float = 0.35
    ghost_scenario_provider: str = "cpu"
    ghost_simulator_provider: str = "mujoco_cpu"
    ghost_judge_provider: str = "cpu"
    ghost_cpu_model_review_enabled: bool = False
    ghost_agent_model_review_enabled: bool = False
    ghost_cpu_model_review_reservation_cents: int = Field(default=10, ge=1, le=200)
    ghost_cpu_model_review_max_tokens: int = Field(default=512, ge=128, le=1024)
    ghost_cpu_model_review_timeout_seconds: float = Field(default=20, ge=1, le=60)
    ghost_policy_name: str = "gantry-push-v1"
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_super_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_ultra_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    scenario_reasoner_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    scenario_reasoner_api_key: str | None = None
    scenario_reasoner_model: str = "nvidia/nemotron-3-super-120b-a12b"
    cosmos_base_url: str | None = None
    cosmos_api_key: str | None = None
    nvidia_api_key: str | None = None
    cosmos_api_style: str = "nim"
    cosmos_timeout_seconds: float = 1800
    cosmos_resolution: str = "480_16_9"
    cosmos_num_frames: int = 121
    cosmos_fps: float = 24.0
    cosmos_steps: int = 35
    cosmos_guidance_scale: float = 6.0
    isaac_job_endpoint: str | None = None
    isaac_job_token: str | None = None
    isaac_job_timeout_seconds: float = 1800
    isaac_poll_interval_seconds: float = 2.0
    isaac_worker_expected_backend: str | None = None
    isaac_worker_expected_commit: str | None = None
    gr00t_checkpoint: str | None = None
    gr00t_checkpoint_digest: str | None = None
    gr00t_policy_host: str = "127.0.0.1"
    gr00t_policy_port: int = 5550
    ghost_execution_backend: str = "mujoco_cpu"
    ghost_admin_token: str | None = None
    ghost_operator_token: str | None = None
    ghost_viewer_token: str | None = None
    ghost_allowed_origins: str = ""
    ghost_live_execution_enabled: bool = False
    ghost_max_pending_jobs: int = Field(default=10, ge=1, le=1000)
    ghost_max_jobs_per_day: int = Field(default=20, ge=1, le=10000)
    ghost_max_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    ghost_job_timeout_seconds: float = Field(default=3900, ge=1, le=86400)
    ghost_session_seconds: int = Field(default=3600, ge=60, le=86400)
    ghost_cookie_secure: bool = True
    ghost_model_max_tokens: int = Field(default=2048, ge=256, le=8192)
    ghost_artifact_bucket: str | None = None
    ghost_s3_endpoint: str | None = None
    ghost_s3_region: str = "us-east-1"
    privy_app_id: str | None = None
    privy_client_id: str | None = None
    privy_verification_key: str | None = None
    ghost_auth_provider: Literal["privy", "dynamic"] = "privy"
    dynamic_environment_id: str | None = None
    dynamic_jwt_audience: str | None = None
    ghost_customer_auth_required: bool = False
    ghost_unauthenticated_local_dev: bool = False
    ghost_public_deployment: bool = False
    ghost_public_signup_enabled: bool = True
    ghost_privy_session_seconds: int = Field(default=3600, ge=60, le=86400)
    ghost_platform_budget_cents: int = Field(default=0, ge=0)
    ghost_live_job_reservation_cents: int = Field(default=0, ge=0)
    ghost_provider_spending_controls_confirmed: bool = False
    ghost_physical_max_bundle_bytes: int = Field(default=268435456, ge=1048576, le=1073741824)
    ghost_physical_disk_reserve_bytes: int = Field(default=1073741824, ge=10485760)
    ghost_physical_max_chunks_per_minute: int = Field(default=240, ge=1, le=2000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
