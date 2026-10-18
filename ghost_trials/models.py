from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScoreCategory(StrEnum):
    AVOIDED = "avoided"
    MITIGATED = "mitigated"
    FAILED = "failed"
    CATASTROPHIC = "catastrophic"
    INSUFFICIENT = "insufficient_evidence"


class TrialStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    SIMULATING = "simulating"
    SCORING = "scoring"
    DONE = "done"
    ERROR = "error"
    BLOCKED = "blocked"
    RECORDED = "recorded"


class StructuredDescription(BaseModel):
    objects: list[str]
    hazard_type: str
    severity: Severity
    expected_safe_behavior: str


class Scenario(BaseModel):
    organization_id: str = "legacy"
    scenario_id: str
    prompt: str
    structured_description: StructuredDescription
    video_url: str | None = None
    severity_tag: Severity
    seed: int
    requested_severity: Severity | None = None
    execution_recipe: dict | None = None
    generation_provenance: dict | None = None
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceEvent(BaseModel):
    kind: Literal["hazard_onset", "reaction", "closest_approach", "collision", "fall", "outcome"]
    timestamp_ms: float = Field(ge=0, allow_inf_nan=False)
    description: str


class TrialMetrics(BaseModel):
    time_to_react_ms: int | None = Field(ge=0)
    min_clearance_m: float | None = Field(ge=0, allow_inf_nan=False)
    max_contact_slip_speed_m_s: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    effective_friction: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    task_completed: bool
    fall_or_collision: bool
    intervention_count: int = Field(default=0, ge=0)
    observation_window_ms: int | None = Field(default=None, ge=0)
    metric_basis: str | None = None
    measurements_are_proxies: bool = True
    simulation_video_url: str | None = Field(default=None,
        description="Legacy response-video field: physical recordings point to uploaded camera footage, not simulation.")
    trajectory_url: str | None = Field(default=None, description="State-derived visualization; not camera footage.")
    trace_url: str | None = None
    simulator_version: str | None = None
    policy_checkpoint_digest: str | None = None
    evidence_origin: Literal["synthetic", "simulator", "physical", "unknown"] = "unknown"
    hardware_provenance: dict | None = None
    events: list[EvidenceEvent] = Field(default_factory=list)
    artifact_manifest: dict = Field(default_factory=dict)
    robot_metrics: dict | None = Field(default=None, description="Task-specific measurements derived from simulator state.")


class JudgeResult(BaseModel):
    score_category: ScoreCategory
    confidence: float = Field(ge=0, le=1)
    reasoning_trace: str
    tier_used: str


class ModelReview(BaseModel):
    status: Literal["complete", "disabled", "unavailable", "budget_exhausted", "provider_error", "invalid_response"]
    model_id: str | None = None
    evidence_digest: str | None = None
    suggested_outcome: Literal["pass", "fail", "insufficient_evidence"] | None = None
    interpretation: str | None = None
    cited_metrics: dict[str, float | bool] = Field(default_factory=dict)
    self_reported_confidence: float | None = Field(default=None, ge=0, le=1)
    disagrees_with_measurement: bool = False
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    reviewed_at: datetime | None = None


class Trial(BaseModel):
    organization_id: str = "legacy"
    trial_id: str
    scenario_id: str
    embodiment: str = "UNITREE_G1_SONIC"
    policy_name: str = "g1_warehouse_v3"
    status: TrialStatus = TrialStatus.QUEUED
    metrics: TrialMetrics | None = None
    score_category: ScoreCategory | None = None
    confidence: float | None = None
    tier_used: str | None = None
    reasoning_trace: str | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    rubric_version: str = "legacy-unversioned"
    judge_assessment: JudgeResult | None = None
    model_review: ModelReview | None = None
    replay_of: str | None = None
    execution_mode: Literal["simulation", "physical"] = "simulation"
    physical_session_id: str | None = None
    evidence_verification: dict | None = None


class TrialView(Trial):
    scenario: Scenario
    evidence_class: str = "unverified"
    score_eligible: bool = False
    score_exclusion_reasons: list[str] = Field(default_factory=list)


class ScenarioCreate(BaseModel):
    prompt: str = Field(min_length=8, max_length=400)
    severity: Severity | None = None
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class PipelineAccepted(BaseModel):
    scenario: Scenario
    trial: Trial


class SafetyScore(BaseModel):
    policy_name: str
    n_trials: int
    distribution: dict[str, int]
    safety_score: float | None
    score_kind: Literal["task_success_rate", "legacy_weighted_evaluation"] = "legacy_weighted_evaluation"
    scored_trials: int = 0
    excluded_trials: int = 0
    score_available: bool = True
    groups: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)


class LiveEvent(BaseModel):
    event: Literal["trial_update"] = "trial_update"
    trial_id: str
    status: TrialStatus
    score_category: ScoreCategory | None = None
    message: str
