"""
GNONE — Unified Configuration Manager.
Centralized environment variable loading and validation.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class GNONEConfig(BaseSettings):
    """Unified configuration for all GNONE system components."""

    # API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API key")
    STRIPE_API_KEY: str = Field(default="", description="Stripe API key for billing")
    LIVEKIT_API_KEY: str = Field(default="", description="LiveKit API key")
    LIVEKIT_API_SECRET: str = Field(default="", description="LiveKit API secret")
    RECALL_AI_API_KEY: str = Field(default="", description="Recall.ai API key")

    # Encryption
    SEPE_MASTER_KEY: str = Field(
        default="",
        description="32-byte hex AES-256-GCM master key for vault decryption"
    )
    ENCRYPTION_KEY: str = Field(
        default="0" * 64,
        description="Legacy encryption key (fallback)"
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://gnone:gnone@localhost:5432/gnone",
        description="Async PostgreSQL connection string"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for task queues"
    )

    # Vector Store
    CHROMA_DB_PATH: str = Field(
        default="data/vector_store",
        description="Local ChromaDB persistence directory"
    )

    # LiveKit
    LIVEKIT_HOST: str = Field(
        default="https://gnone.livekit.cloud",
        description="LiveKit server host"
    )

    # Environment
    ENVIRONMENT: str = Field(default="development", description="deployment environment")
    HOST: str = Field(default="0.0.0.0", description="FastAPI bind host")
    PORT: int = Field(default=8000, description="FastAPI bind port")
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # Google Blogger
    GOOGLE_BLOGGER_BLOG_ID: str = Field(default="default", description="Blogger blog ID")

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4318/v1/traces",
        description="OTLP trace endpoint"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def validate_master_key(self) -> str:
        """Validate AES-256-GCM master key is properly formatted."""
        key = self.SEPE_MASTER_KEY or self.ENCRYPTION_KEY
        if not key:
            raise ValueError("SEPE_MASTER_KEY or ENCRYPTION_KEY must be set")
        try:
            key_bytes = bytes.fromhex(key)
        except ValueError:
            raise ValueError("Master key is not a valid hexadecimal string")
        if len(key_bytes) != 32:
            raise ValueError(f"Master key must be exactly 32 bytes (64 hex chars), got {len(key_bytes)}")
        return key

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def data_dir(self) -> Path:
        return Path("data")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def vector_store_dir(self) -> Path:
        return self.data_dir / "vector_store"

    @property
    def log_dir(self) -> Path:
        return Path("logs")

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.data_dir, self.uploads_dir, self.vector_store_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)


config = GNONEConfig()
config.ensure_directories()
