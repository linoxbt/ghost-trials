from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Literal types make a typo (e.g. GHOST_MODE=prod) a startup error instead of silently skipping checks.
    ghost_mode: Literal["local", "cpu", "production"] = "cpu"
    ghost_data_path: Path = Path("data/state.json")
    ghost_artifact_root: Path = Path("artifacts/generated")
    # On Railway, refuse to start unless state and artifacts live on the attached volume.
    ghost_require_persistent_data: bool = True
    ghost_pipeline_delay_seconds: float = 0.35
    ghost_scenario_provider: Literal["local", "cpu", "cosmos"] = "cpu"
    ghost_simulator_provider: Literal["local", "mujoco_cpu", "isaac_http"] = "mujoco_cpu"
    ghost_judge_provider: Literal["local", "cpu", "nebius"] = "cpu"
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
    cosmos_api_style: Literal["nim", "vllm", "nvidia_catalog"] = "nim"
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
    isaac_worker_expected_commit: str | None = None
    gr00t_checkpoint: str | None = None
    gr00t_checkpoint_digest: str | None = None
    gr00t_policy_host: str = "127.0.0.1"
    gr00t_policy_port: int = 5550
    ghost_execution_backend: Literal["mujoco_cpu", "gear_sonic_sim", "isaac_arena_gr00t"] = "mujoco_cpu"
    ghost_admin_token: str | None = None
    ghost_operator_token: str | None = None
    ghost_viewer_token: str | None = None
    ghost_allowed_origins: str = ""
    ghost_live_execution_enabled: bool = False
    # Platform-wide backstops; the per-organization caps below are what one workspace can use.
    ghost_max_pending_jobs: int = Field(default=10, ge=1, le=1000)
    ghost_max_jobs_per_day: int = Field(default=300, ge=1, le=100000)
    ghost_max_org_pending_jobs: int = Field(default=2, ge=1, le=1000)
    ghost_max_org_jobs_per_day: int = Field(default=40, ge=1, le=10000)
    # One person across all of their workspaces, so self-service sign-up cannot drain the platform cap.
    ghost_max_subject_pending_jobs: int = Field(default=2, ge=1, le=1000)
    ghost_max_subject_jobs_per_day: int = Field(default=60, ge=1, le=10000)
    ghost_max_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    ghost_max_anonymous_requests_per_minute: int = Field(default=600, ge=1, le=100000)
    ghost_max_client_auth_attempts_per_minute: int = Field(default=10, ge=1, le=1000)
    # Platform-wide sign-in backstop, kept well below the anonymous request backstop.
    ghost_max_auth_attempts_per_minute: int = Field(default=60, ge=1, le=10000)
    # Number of trusted reverse proxies that append to X-Forwarded-For (0 = use the socket peer).
    ghost_trusted_proxy_hops: int = Field(default=0, ge=0, le=5)
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
    ghost_physical_org_storage_bytes: int = Field(default=1073741824, ge=1048576)
    ghost_physical_platform_storage_bytes: int = Field(default=4294967296, ge=1048576)
    ghost_physical_pending_ttl_seconds: int = Field(default=86400, ge=60)
    ghost_physical_max_chunks_per_minute: int = Field(default=240, ge=1, le=2000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
