"""
GNONE — Unified Database Models.
PostgreSQL + pgvector ORM schemas with ChromaDB fallback support.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, Numeric,
    ForeignKey, DateTime, LargeBinary, Index, CheckConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


# ===========================================================================
# DATABASE ENGINE
# ===========================================================================

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


async def initialize_database(db_url: str, echo: bool = False) -> AsyncEngine:
    """Initialize async PostgreSQL connection pool with pgvector extension."""
    global _engine, _session_maker

    if not db_url.startswith("postgresql"):
        raise ValueError(
            f"Database dialect must be PostgreSQL. Received: '{db_url.split('://')[0]}'"
        )

    _engine = create_async_engine(
        db_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )

    _session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)

    logger.info("PostgreSQL database initialized successfully.")
    return _engine


async def get_db_session() -> AsyncSession:
    """Yield an async database session with automatic commit/rollback."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    async with _session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ===========================================================================
# ACCOUNT & AUTH
# ===========================================================================

class Account(Base):
    """Executive organizational account profile."""
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="starter")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_content_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    config_constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    oauth_vault_entries: Mapped[List["OAuthVault"]] = relationship("OAuthVault", back_populates="account", cascade="all, delete-orphan")
    persona_registries: Mapped[List["PersonaRegistry"]] = relationship("PersonaRegistry", back_populates="account", cascade="all, delete-orphan")
    knowledge_vectors: Mapped[List["CorporateKnowledgeVector"]] = relationship("CorporateKnowledgeVector", back_populates="account", cascade="all, delete-orphan")
    content_state_ledgers: Mapped[List["ContentStateLedger"]] = relationship("ContentStateLedger", back_populates="account", cascade="all, delete-orphan")
    financial_ledgers: Mapped[List["FinancialLedger"]] = relationship("FinancialLedger", back_populates="account", cascade="all, delete-orphan")
    workspace_documents: Mapped[List["WorkspaceDocument"]] = relationship("WorkspaceDocument", back_populates="account", cascade="all, delete-orphan")
    dag_execution_ledgers: Mapped[List["DagExecutionLedger"]] = relationship("DagExecutionLedger", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("subscription_tier IN ('starter', 'growth', 'enterprise')", name="ck_account_tier"),
        CheckConstraint("daily_content_quota > 0", name="ck_account_quota"),
    )


class OAuthVault(Base):
    """AES-256-GCM encrypted social API credential vault."""
    __tablename__ = "oauth_vault"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="oauth_vault_entries")

    __table_args__ = (Index("idx_oauth_account_platform", "account_id", "platform", unique=True),)


# ===========================================================================
# PERSONA & KNOWLEDGE
# ===========================================================================

class PersonaRegistry(Base):
    """Digital clone persona registry with negotiation thresholds."""
    __tablename__ = "persona_registry"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voice_clone_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negotiation_floor_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=50000.00)
    guardrails: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="persona_registries")
    content_state_ledgers: Mapped[List["ContentStateLedger"]] = relationship("ContentStateLedger", back_populates="persona", cascade="all, delete-orphan")


class CorporateKnowledgeVector(Base):
    """pgvector HNSW index for corporate documentation RAG."""
    __tablename__ = "corporate_knowledge_vectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="document")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(String(1536), nullable=False)  # Vector(1536) requires pgvector
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="knowledge_vectors")


# ===========================================================================
# CONTENT & DAG LEDGERS
# ===========================================================================

class ContentStateLedger(Base):
    """State machine ledger for content draft lifecycle tracking."""
    __tablename__ = "content_state_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persona_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HUMAN_SIGN_OFF")
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    refinement_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    original_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("content_state_ledger.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="content_state_ledgers")
    persona: Mapped["PersonaRegistry"] = relationship("PersonaRegistry", back_populates="content_state_ledgers")

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_HUMAN_SIGN_OFF', 'APPROVED', 'REJECTED', 'DEPLOYED', 'FAILED')",
            name="ck_content_status",
        ),
        Index("idx_ledger_account_status", "account_id", "status"),
    )


class DagExecutionLedger(Base):
    """Telemetry tracker for non-linear JSON DAG executions."""
    __tablename__ = "dag_execution_ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    macro_goal: Mapped[str] = mapped_column(String(255), nullable=False)
    dag_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    telemetry_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="dag_execution_ledgers")


# ===========================================================================
# FINANCIAL & WORKSPACE
# ===========================================================================

class FinancialLedger(Base):
    """Corporate asset, expense, salary, and invoice tracking."""
    __tablename__ = "financial_ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("workspace_documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="financial_ledgers")
    source_document: Mapped[Optional["WorkspaceDocument"]] = relationship("WorkspaceDocument")


class WorkspaceDocument(Base):
    """Executive document, contract, and file tracking."""
    __tablename__ = "workspace_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    vector_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unindexed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="workspace_documents")
