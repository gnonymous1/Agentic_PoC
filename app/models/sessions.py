from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SessionStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeetingPlatform(str, Enum):
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    TEAMS = "teams"
    WEBEX = "webex"


class DealStage(str, Enum):
    DISCOVERY = "discovery"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class ProxySessionCreate(BaseModel):
    client_id: str
    agent_profile_id: str | None = None
    meeting_platform: MeetingPlatform = MeetingPlatform.ZOOM
    meeting_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("client_id")
    @classmethod
    def client_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("client_id must not be empty")
        return v.strip()


class ProxySessionResponse(BaseModel):
    id: str
    client_id: str
    agent_profile_id: str | None = None
    recall_session_id: str | None = None
    livekit_room_name: str | None = None
    meeting_platform: str
    meeting_title: str | None = None
    status: SessionStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    transcript_text: str | None = None
    transcript_summary: str | None = None
    revenue_closed: float = 0.0
    deal_currency: str = "USD"
    deal_stage: str = "discovery"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("duration_seconds")
    @classmethod
    def duration_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("duration_seconds must be non-negative")
        return v

    @field_validator("revenue_closed")
    @classmethod
    def revenue_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("revenue_closed must be non-negative")
        return v

    @field_validator("deal_currency")
    @classmethod
    def currency_code_uppercase(cls, v: str) -> str:
        if v and len(v) != 3:
            raise ValueError("deal_currency must be a 3-letter ISO currency code")
        return v.upper()


class SessionAnalytics(BaseModel):
    total_sessions: int
    active_sessions: int
    completed_sessions: int
    total_revenue: float
    avg_duration_seconds: float
    completion_rate: float

    @field_validator("total_sessions", "active_sessions", "completed_sessions")
    @classmethod
    def counts_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("session counts must be non-negative")
        return v

    @field_validator("completion_rate")
    @classmethod
    def rate_in_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("completion_rate must be between 0.0 and 1.0")
        return v

    @field_validator("total_revenue", "avg_duration_seconds")
    @classmethod
    def values_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("financial and duration values must be non-negative")
        return v
