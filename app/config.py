import os

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_temperature: float = 0.3
    gemini_top_p: float = 0.7
    gemini_top_k: int = 20
    gemini_max_output_tokens: int = 8192

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    generator_model: str = "deepseek/deepseek-v4-flash:free"
    generator_fallback_model: str = "nousresearch/hermes-3-llama-3.1-405b:free"
    generator_fallback_model_2: str = "poolside/laguna-m.1:free"
    generator_fallback_model_3: str = "baidu/cobuddy:free"
    generator_temperature: float = 0.4
    generator_max_tokens: int = 8192

    critic_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    critic_eval_temperature: float = 0.0
    critic_correct_temperature: float = 0.3
    critic_max_tokens: int = 4096

    max_retries: int = 2
    request_timeout_seconds: int = 120
    agent_timeout_seconds: int = 90
    deadline_buffer_seconds: int = 20

    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")

    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")
    livekit_host: str = os.getenv("LIVEKIT_HOST", "https://gnone.livekit.cloud")

    recall_ai_api_key: str = os.getenv("RECALL_AI_API_KEY", "")
    recall_ai_base_url: str = os.getenv("RECALL_AI_BASE_URL", "https://api.recall.ai/v1")

    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_key(cls, v: str) -> str:
        if v and len(v) < 16:
            raise ValueError("GEMINI_API_KEY appears to be truncated")
        return v

    @field_validator("openrouter_api_key")
    @classmethod
    def validate_openrouter_key(cls, v: str) -> str:
        if v and len(v) < 16:
            raise ValueError("OPENROUTER_API_KEY appears to be truncated")
        return v

    @field_validator("livekit_api_key")
    @classmethod
    def validate_livekit_key(cls, v: str) -> str:
        if v and len(v) < 8:
            raise ValueError("LIVEKIT_API_KEY appears to be truncated")
        return v

    @field_validator("recall_ai_api_key")
    @classmethod
    def validate_recall_key(cls, v: str) -> str:
        if v and len(v) < 8:
            raise ValueError("RECALL_AI_API_KEY appears to be truncated")
        return v


settings = Settings()
