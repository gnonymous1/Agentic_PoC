"""
SEPE — Sovereign Executive Persona Clone (SEPE)
Production Persistence Layer & PostgreSQL Storage Schemas

This module defines the production-ready SQLAlchemy 2.0 ORM schemas for the platform.
It enforces native PostgreSQL pgvector HNSW storage and requires valid AES-256-GCM configurations.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Float,
    Numeric,
    ForeignKey,
    DateTime,
    LargeBinary,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

# Enforce pgvector import in production
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    raise ImportError(
        "Production environment requires 'pgvector' library installed. "
        "Run: pip install pgvector"
    )

logger = logging.getLogger(__name__)

# ===========================================================================
# 1. ORM declarative base
# ===========================================================================

class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


# ===========================================================================
# 2. RUNTIME CRYPTOGRAPHIC ENVIRONMENT VALIDATION
# ===========================================================================

def validate_production_master_key() -> str:
    """
    Enforces AES-256-GCM runtime environment validation boundaries.
    Retrieves and checks the 256-bit symmetric key from system variables.
    """
    key_hex = os.getenv("SEPE_MASTER_KEY")
    if not key_hex:
        raise ValueError(
            "CRITICAL SECURITY FAILURE: Environment variable 'SEPE_MASTER_KEY' is not set. "
            "Production deployments require a valid 256-bit AES Master Key for vault decryption."
        )
    try:
        key_bytes = bytes.fromhex(key_hex)
    except ValueError:
        raise ValueError(
            "CRITICAL SECURITY FAILURE: 'SEPE_MASTER_KEY' is not a valid hexadecimal string."
        )
    if len(key_bytes) != 32:
        raise ValueError(
            f"CRITICAL SECURITY FAILURE: 'SEPE_MASTER_KEY' must be exactly 32 bytes (64 hex characters). "
            f"Current size is {len(key_bytes)} bytes."
        )
    return key_hex


# ===========================================================================
# 3. PRODUCTION SCHEMAS (PostgreSQL Only)
# ===========================================================================

class Account(Base):
    """
    Executive organizational account profile.
    Maintains primary administrative boundaries, billing limits, and active status rules.
    """
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="starter")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_content_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    config_constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    oauth_vault_entries: Mapped[List["OAuthVault"]] = relationship(
        "OAuthVault", back_populates="account", cascade="all, delete-orphan"
    )
    persona_registries: Mapped[List["PersonaRegistry"]] = relationship(
        "PersonaRegistry", back_populates="account", cascade="all, delete-orphan"
    )
    knowledge_vectors: Mapped[List["CorporateKnowledgeVector"]] = relationship(
        "CorporateKnowledgeVector", back_populates="account", cascade="all, delete-orphan"
    )
    content_state_ledgers: Mapped[List["ContentStateLedger"]] = relationship(
        "ContentStateLedger", back_populates="account", cascade="all, delete-orphan"
    )
    financial_ledgers: Mapped[List["FinancialLedger"]] = relationship(
        "FinancialLedger", back_populates="account", cascade="all, delete-orphan"
    )
    workspace_documents: Mapped[List["WorkspaceDocument"]] = relationship(
        "WorkspaceDocument", back_populates="account", cascade="all, delete-orphan"
    )
    dag_execution_ledgers: Mapped[List["DagExecutionLedger"]] = relationship(
        "DagExecutionLedger", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            subscription_tier.in_(["starter", "growth", "enterprise"]),
            name="ck_account_subscription_tier",
        ),
        CheckConstraint("daily_content_quota > 0", name="ck_account_daily_quota"),
    )


class OAuthVault(Base):
    """
    Secure Encrypted Vault for long-lived social communication and API credentials.
    Decryptable strictly in memory using AES-256-GCM.
    """
    __tablename__ = "oauth_vault"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'meta', 'x', 'blogspot'
    
    # Authenticated Encryption Fields (AES-256-GCM payloads)
    encrypted_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="oauth_vault_entries")

    __table_args__ = (
        Index("idx_oauth_vault_account_platform", "account_id", "platform", unique=True),
    )


class PersonaRegistry(Base):
    """
    Clone persona registry mapping physical business executives to their digital twins.
    Includes explicit minimum B2B contract value limits.
    """
    __tablename__ = "persona_registry"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voice_clone_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Negotiation deal threshold
    negotiation_floor_price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=50000.00
    )
    
    guardrails: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="persona_registries")
    content_state_ledgers: Mapped[List["ContentStateLedger"]] = relationship(
        "ContentStateLedger", back_populates="persona", cascade="all, delete-orphan"
    )


class CorporateKnowledgeVector(Base):
    """
    Multi-tenant corporate documentation vector store.
    Utilizes PostgreSQL's pgvector extension with HNSW indexes and vector_cosine_ops.
    """
    __tablename__ = "corporate_knowledge_vectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="document")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Production-ready 1536-dimensional native PostgreSQL Vector
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="knowledge_vectors")

    __table_args__ = (
        Index(
            "idx_corporate_knowledge_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ContentStateLedger(Base):
    """
    State machine workflow ledger tracking the lifecycle of executive clones' content drafts.
    """
    __tablename__ = "content_state_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persona_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'content_publish', 'proposal_generation'
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING_HUMAN_SIGN_OFF"
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON formatted platform draft
    refinement_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'meta', 'x', 'blogspot'
    original_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("content_state_ledger.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="content_state_ledgers")
    persona: Mapped["PersonaRegistry"] = relationship("PersonaRegistry", back_populates="content_state_ledgers")

    __table_args__ = (
        CheckConstraint(
            status.in_(["PENDING_HUMAN_SIGN_OFF", "APPROVED", "REJECTED", "DEPLOYED", "FAILED"]),
            name="ck_content_ledger_status",
        ),
        Index("idx_ledger_account_status", "account_id", "status"),
    )


# ===========================================================================
# 4. DIGITAL CLONE MASTER ORCHESTRATOR SCHEMA EXTENSIONS
# ===========================================================================

class FinancialLedger(Base):
    """
    Tracks direct corporate assets, expenses, salary arrears, and invoice payments.
    """
    __tablename__ = "financial_ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'receivable', 'payable', 'expense'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # 'pending', 'cleared', 'anomaly'
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("workspace_documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="financial_ledgers")
    source_document: Mapped[Optional["WorkspaceDocument"]] = relationship("WorkspaceDocument")


class WorkspaceDocument(Base):
    """
    Tracks executive folders, corporate documents, contract PDFs, and text sheets.
    """
    __tablename__ = "workspace_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'pdf', 'csv', 'md', 'txt'
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    vector_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unindexed")  # 'unindexed', 'indexed'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="workspace_documents")


class DagExecutionLedger(Base):
    """
    Maintains telemetry logs and status trackers for non-linear JSON execution DAGs.
    """
    __tablename__ = "dag_execution_ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    macro_goal: Mapped[str] = mapped_column(String(255), nullable=False)
    dag_json: Mapped[str] = mapped_column(Text, nullable=False)  # Compiled multi-layer JSON tree
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")  # 'running', 'completed', 'failed', 'pending_approval'
    telemetry_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="dag_execution_ledgers")


# ===========================================================================
# 5. DATABASE INITIALIZATION ENGINE
# ===========================================================================

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


async def initialize_database(db_url: str, echo: bool = False) -> AsyncEngine:
    """
    Initializes the production database connection pool.
    Verifies that the target database dialect is strictly PostgreSQL and registers Vector extensions.
    Also runs AES Master Key environment validations.
    """
    global _engine, _session_maker
    
    # 1. Enforce Master Key validation at startup
    validate_production_master_key()
    
    # 2. Enforce absolute PostgreSQL dialect constraints
    if not db_url.startswith("postgresql"):
        raise ValueError(
            f"PRODUCTION ENVIRONMENT EXCLUSION: The database dialect must be strictly PostgreSQL. "
            f"Received dialet was: '{db_url.split('://')[0]}'. "
            f"SQLite or standard file engines are restricted in production deployment scopes."
        )
        
    _engine = create_async_engine(
        db_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10
    )
    
    _session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create extension schemas and ORM tables
    async with _engine.begin() as conn:
        logger.info("Enforcing PostgreSQL Vector extensions...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        logger.info("Initializing metadata tables...")
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("SEPE PostgreSQL connection established and initialized successfully.")
    return _engine


async def get_db_session() -> AsyncSession:
    """Retrieves an active database transaction session from the connection pool."""
    if _session_maker is None:
        raise RuntimeError("Database engine has not been initialized. Call initialize_database() first.")
    async with _session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
