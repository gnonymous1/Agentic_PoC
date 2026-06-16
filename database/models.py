"""
SQLAlchemy 2.0 ORM models for the Sovereign Executive Proxy Engine.
Maps to the existing multi-tenant migration schema plus new HITL/voice tables.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Float,
    Numeric,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    Enum as SAEnum,
    DateTime,
    JSON,
    LargeBinary,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from pgvector.sqlalchemy import VECTOR
from database.connection import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_name: Mapped[str] = mapped_column(Text, nullable=False)
    org_slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    billing_email: Mapped[str] = mapped_column(Text, nullable=False)
    subscription_tier: Mapped[str] = mapped_column(
        Text, nullable=False, default="starter"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_content_quota: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    oauth_tokens: Mapped[list["OAuthVault"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    agent_profiles: Mapped[list["AgentProfile"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["ProxySession"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    knowledge_vectors: Mapped[list["CorporateKnowledgeVector"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    hitl_actions: Mapped[list["HitlAction"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    voice_clone_jobs: Mapped[list["VoiceCloneJob"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            subscription_tier.in_(["starter", "growth", "enterprise"]),
            name="ck_client_tier",
        ),
        CheckConstraint("daily_content_quota > 0", name="ck_client_quota"),
        Index("idx_clients_org_slug", org_slug),
        Index("idx_clients_is_active", is_active, postgresql_where=is_active.is_(True)),
    )


class OAuthVault(Base):
    __tablename__ = "oauth_vault"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    platform_label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    encrypted_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_type: Mapped[str] = mapped_column(Text, nullable=False, default="bearer")
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scopes: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=list)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="oauth_tokens")

    __table_args__ = (
        Index("idx_oauth_vault_client", client_id, platform),
    )


class AgentProfile(Base):
    """Persona profile — each entry is a distinct digital twin for a client."""

    __tablename__ = "agent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    voice_clone_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voice_speed: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    guardrails: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="agent_profiles")

    __table_args__ = (
        Index("idx_agent_profiles_client", client_id, is_active),
    )


class ProxySession(Base):
    __tablename__ = "proxy_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    agent_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    recall_session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
    livekit_room_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meeting_platform: Mapped[str] = mapped_column(
        Text, nullable=False, default="zoom"
    )
    meeting_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="PENDING_REVIEW"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transcript_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revenue_closed: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.00
    )
    deal_currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    deal_stage: Mapped[str] = mapped_column(
        Text, nullable=False, default="discovery"
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="sessions")

    __table_args__ = (
        CheckConstraint(
            meeting_platform.in_(["zoom", "google_meet", "teams", "webex"]),
            name="ck_session_platform",
        ),
        CheckConstraint(
            deal_stage.in_(
                ["discovery", "negotiation", "closed_won", "closed_lost"]
            ),
            name="ck_session_deal_stage",
        ),
        Index("idx_proxy_sessions_client", client_id, status),
    )


class CorporateKnowledgeVector(Base):
    __tablename__ = "corporate_knowledge_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="document"
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(1536), nullable=False
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="knowledge_vectors")

    __table_args__ = (
        Index(
            "idx_corporate_knowledge_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_ckv_client_source", client_id, source_type),
    )


class HitlAction(Base):
    """
    Human-in-the-Loop workflow ledger.
    Every automated clone action is recorded here with a status state machine.
    """

    __tablename__ = "hitl_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    agent_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="social_post | email_reply | comment_reply | meeting_action | content_publish",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="PENDING_HUMAN_SIGN_OFF",
        comment="PENDING_HUMAN_SIGN_OFF | APPROVED | REJECTED | REWRITE_IN_PROGRESS | REWRITE_COMPLETED | DEPLOYED | FAILED",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="The drafted content / action payload",
    )
    refinement_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Critic or human rejection notes for rewrite loop",
    )
    target_platform: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="meta | x | linkedin | google_blogger | email | zoom",
    )
    original_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="If this is a rewrite, references the original HitlAction id",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deployed_response: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="API response from the platform deployment",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="hitl_actions")

    __table_args__ = (
        CheckConstraint(
            status.in_([
                "PENDING_HUMAN_SIGN_OFF",
                "APPROVED",
                "REJECTED",
                "REWRITE_IN_PROGRESS",
                "REWRITE_COMPLETED",
                "DEPLOYED",
                "FAILED",
            ]),
            name="ck_hitl_status",
        ),
        Index("idx_hitl_client_status", client_id, status),
        Index("idx_hitl_pending", status, postgresql_where=status == "PENDING_HUMAN_SIGN_OFF"),
    )


class VoiceCloneJob(Base):
    """
    Tracks voice cloning lifecycle.
    Upload samples → trigger training → poll → store voice_model_id.
    """

    __tablename__ = "voice_clone_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    agent_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(
        Text, nullable=False, default="elevenlabs",
        comment="elevenlabs | cartesia | playht",
    )
    voice_name: Mapped[str] = mapped_column(Text, nullable=False)
    sample_file_path: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Path or URL to the uploaded WAV sample",
    )
    sample_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="PENDING_UPLOAD",
        comment="PENDING_UPLOAD | UPLOADED | TRAINING | ACTIVE | FAILED",
    )
    provider_job_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Job ID returned by ElevenLabs/Cartesia",
    )
    voice_model_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Final voice model ID for TTS inference",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="voice_clone_jobs")

    __table_args__ = (
        Index("idx_voice_jobs_client", client_id, status),
    )
