from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ghost_mode: str = "local"
    ghost_data_path: Path = Path("data/state.json")
    ghost_artifact_root: Path = Path("artifacts/generated")
    ghost_pipeline_delay_seconds: float = 0.35
    ghost_scenario_provider: str = "local"
    ghost_simulator_provider: str = "local"
    ghost_judge_provider: str = "local"
    ghost_policy_name: str = "configured-g1-policy"
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_super_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_ultra_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    scenario_reasoner_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    scenario_reasoner_api_key: str | None = None
    scenario_reasoner_model: str = "nvidia/nemotron-3-super-120b-a12b"
    cosmos_base_url: str | None = None
    cosmos_api_key: str | None = None
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
    ghost_execution_backend: str = "gear_sonic_sim"


@lru_cache
def get_settings() -> Settings:
    return Settings()
