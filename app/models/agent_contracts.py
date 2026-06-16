"""
Strongly typed data contracts enforced between agents in the DAG pipeline.
Each contract defines the exact shape of data an agent expects as input
and guarantees as output — enforced via Pydantic at runtime.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ResearchContract(BaseModel):
    """Contract between Research Agent → Copywriting Agent."""
    topic: str
    unified_truth_document: str = Field(..., min_length=200)
    source_domains: list[str] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("unified_truth_document")
    @classmethod
    def validate_utd_length(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count < 50:
            raise ValueError(f"UTD too short: {word_count} words, minimum 50")
        return v


class CopywritingContract(BaseModel):
    """Contract between Copywriting Agent → Critic Agent."""
    utd_summary: str = Field(..., max_length=500)
    twitter_thread: list[str] = Field(..., min_length=5, max_length=10)
    linkedin_body: str = Field(..., min_length=50)
    facebook_body: str = Field(..., min_length=50)
    blogspot_html: str = Field(..., min_length=300)

    @field_validator("twitter_thread")
    @classmethod
    def validate_twitter_lengths(cls, v: list[str]) -> list[str]:
        for i, post in enumerate(v):
            if len(post) > 240:
                raise ValueError(f"Twitter post {i+1} exceeds 240 chars ({len(post)})")
        return v


class CriticVerdict(BaseModel):
    """Contract between Critic Agent → Moderator Agent / Feedback Loop."""
    approved: bool
    refinement_notes: str = ""
    corrected_payloads: dict = Field(default_factory=dict)
    banned_phrases_found: list[str] = Field(default_factory=list)
    structural_issues: list[str] = Field(default_factory=list)
    critic_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ModeratorVerdict(BaseModel):
    """Contract between Moderator Agent → Output Queue."""
    passed_safety_check: bool
    content_safe: bool = True
    flagged_categories: list[str] = Field(default_factory=list)
    moderation_notes: str = ""
    moderated_content: dict | None = None


class DeploymentContract(BaseModel):
    """Contract between Moderator Agent → Platform Dispatchers."""
    request_id: str
    client_id: str
    platform: str
    content_body: str
    scheduled_at: datetime | None = None
    dry_run: bool = False
