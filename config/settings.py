"""
Configuration Management for AgentOS
Loads environment-specific settings from YAML files and environment variables
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///./data/agentos.db")
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)
    pool_timeout: int = Field(default=30)


class RedisConfig(BaseModel):
    """Redis configuration"""
    url: str = Field(default="redis://localhost:6379/0")
    password: Optional[str] = None
    max_connections: int = Field(default=50)


class LLMConfig(BaseModel):
    """LLM configuration"""
    provider: str = Field(default="openrouter")
    api_key: str = Field(default="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")
    openrouter_api_key: Optional[str] = Field(default="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")
    model_name: str = Field(default="arcee-ai/trinity-large-preview:free")
    base_url: Optional[str] = Field(default="https://openrouter.ai/api/v1")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)
    
    # Free tier fallback models
    fallback_models: list[str] = Field(default=[
        "arcee-ai/trinity-large-preview:free",
        "z-ai/glm-4.5-air:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "qwen/qwen3-coder:free"
    ])


class SecurityConfig(BaseModel):
    """Security configuration"""
    secret_key: str = Field(default="dev_secret_key_change_in_production")
    jwt_secret: str = Field(default="dev_jwt_secret_change_in_production")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    allowed_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])

    # Admin User
    admin_password: str = Field(default="admin123")
    admin_email: str = Field(default="admin@agentos.local")


class ObservabilityConfig(BaseModel):
    """Observability configuration"""
    sentry_dsn: Optional[str] = None
    enable_tracing: bool = Field(default=True)
    metrics_retention: int = Field(default=86400)
    log_level: str = Field(default="INFO")


class Settings(BaseSettings):
    """Main application settings"""
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=1)
    
    # Components
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    
    # Channels
    gateway_port: int = Field(default=8765)
    web_channel_port: int = Field(default=8766)
    telegram_bot_token: Optional[str] = None
    
    # Memory
    memory_consolidation_interval: int = Field(default=3600)
    vector_store_path: str = Field(default="./data/chroma")
    
    # Self-Evolution
    evolution_safe_mode: bool = Field(default=True)
    evolution_require_approval: bool = Field(default=True)
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=100)
    memory_wipe_limit_per_minute: int = Field(default=5)
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"


def load_config(environment: Optional[str] = None) -> Settings:
    """
    Load configuration from environment variables and YAML files
    
    Args:
        environment: Environment name (development, staging, production)
        
    Returns:
        Settings object with loaded configuration
    """
    # Determine environment
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    # Load YAML config if exists
    config_dir = Path(__file__).parent
    config_file = config_dir / f"{env}.yaml"
    
    yaml_config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            yaml_config = yaml.safe_load(f) or {}
    
    # Merge with environment variables (env vars take precedence)
    # Pydantic will automatically load from .env file
    settings = Settings(**yaml_config)
    
    # Validate critical settings in production
    if env == "production":
        if settings.security.secret_key.startswith("dev_"):
            raise ValueError("SECRET_KEY must be changed in production!")
        if settings.security.jwt_secret.startswith("dev_"):
            raise ValueError("JWT_SECRET must be changed in production!")
        if not settings.llm.api_key:
            raise ValueError("LLM_API_KEY must be set in production!")
        if settings.security.admin_password == "admin123":
             raise ValueError("Admin password must be changed in production!")
    
    return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance (singleton)"""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


def reload_settings(environment: Optional[str] = None):
    """Reload settings (useful for testing)"""
    global _settings
    _settings = load_config(environment)
    return _settings
