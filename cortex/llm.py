from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import get_settings

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

RECOMMENDED_MODELS = {
    "arcee-ai/trinity-large-preview:free": "Arcee AI: Trinity Large Preview (466B) - High context, agentic",
    "stepfun/step-3.5-flash:free": "StepFun: Step 3.5 Flash (285B) - Speed efficient MoE",
    "z-ai/glm-4.5-air:free": "Z.ai: GLM 4.5 Air (59.7B) - Lightweight, tool-use optimized",
    "deepseek/deepseek-r1:free": "DeepSeek: R1 0528 (671B) - Strong reasoning, open-source",
    "nvidia/nemotron-4-340b-instruct:free": "NVIDIA: Nemotron 3 Nano (Simulated ID) - Agentic, privacy-focused",
}

def get_llm(role: str = "default", temperature: float = 0):
    """
    Factory to get the LLM instance based on Settings.llm.provider and Role.
    """
    settings = get_settings()
    provider = settings.llm.provider.lower()
    
    # Simple model selection for now - can be expanded to role-based later if needed
    model = settings.llm.model_name
    
    api_key = settings.llm.api_key
    
    # Optional base_url for OpenAI-compatible providers
    base_url = None
    if provider in ["ollama", "lm_studio", "openrouter"]:
        # Logic to determine base_url could be added to Settings model if needed
        pass

    print(f"Loading LLM: {model} (Role: {role})")

    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key
        )
    
    elif provider == "groq":
        if ChatGroq is None:
            raise ImportError("Groq provider selected but langchain-groq is not installed. Install requirements-optional.txt.")

        return ChatGroq(
            model_name=model,
            temperature=temperature,
            groq_api_key=api_key,
            max_tokens=settings.llm.max_tokens
        )
        
    elif provider in ["ollama", "lm_studio", "openrouter", "openai"]:
        # Configure specific providers
        if provider == "openrouter":
            base_url = settings.llm.base_url or "https://openrouter.ai/api/v1"
            api_key = settings.llm.openrouter_api_key or settings.llm.api_key
        elif provider == "ollama":
            base_url = settings.llm.base_url or "http://localhost:11434/v1"
        elif provider == "lm_studio":
            base_url = settings.llm.base_url or "http://localhost:1234/v1"
            
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
            max_tokens=settings.llm.max_tokens
        )
    
    else:
        raise ValueError(f"Unsupported LLM Provider: {provider}")
