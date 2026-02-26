import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API & Provider
    API_KEY = os.getenv("LLM_API_KEY") 
    BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
    
    # Memory
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./chroma_db")

    # Model Roles Mapping
    # Free tier models on OpenRouter
    MODEL_ROLES = {
        "default": "arcee-ai/trinity-large-preview:free",
        "thinker": "arcee-ai/trinity-large-preview:free",
        "decider": "arcee-ai/trinity-large-preview:free",
        "reasoner": "z-ai/glm-4.5-air:free",
        "memory": "nvidia/nemotron-3-nano-30b-a3b:free",
        "coder": "qwen/qwen3-coder:free",
        "execution": "arcee-ai/trinity-large-preview:free",
        "interaction": "arcee-ai/trinity-large-preview:free",
        "architect": "z-ai/glm-4.5-air:free",
        "vision": "arcee-ai/trinity-large-preview:free",
        "antigravity": "z-ai/glm-4.5-air:free",
    }
    
    # Available free models for fallback
    FREE_MODELS = [
        "arcee-ai/trinity-large-preview:free",
        "z-ai/glm-4.5-air:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "qwen/qwen3-coder:free"
    ]

