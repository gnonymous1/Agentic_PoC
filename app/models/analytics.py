from datetime import datetime

from pydantic import BaseModel, Field


class ContentAnalyticsEvent(BaseModel):
    event_id: str
    client_id: str
    event_type: str = Field(..., pattern=r"^(content_generated|content_approved|content_rejected|content_published|critic_cycle|error)$")
    platform: str | None = None
    model_used: str | None = None
    latency_ms: float | None = None
    token_count: int | None = None
    refinement_cycle: int = 0
    approved: bool | None = None
    error_type: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class CostReport(BaseModel):
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_tokens_input: int
    total_tokens_output: int
    estimated_cost_usd: float
    cost_by_model: dict[str, float] = Field(default_factory=dict)
    cost_by_client: dict[str, float] = Field(default_factory=dict)


class DashboardSummary(BaseModel):
    total_content_pieces: int
    approval_rate: float
    avg_refinement_cycles: float
    avg_generation_latency_ms: float
    active_clients: int
    total_revenue: float
    error_rate_last_hour: float
    top_platforms: list[dict] = Field(default_factory=list)
    cost_forecast_next_30d: float
