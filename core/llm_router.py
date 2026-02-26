import asyncio
import time
import hashlib
import json
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger("omnios.llm_router")
from core.resilience import ReliabilityManager
from core.caching import CacheManager

class Provider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    TOGETHER = "together"
    DEEPSEEK = "deepseek"
    MISTRAL = "mistral"

@dataclass
class ModelProfile:
    provider: Provider
    model_id: str
    display_name: str
    context_window: int
    cost_per_1k_input: float  # USD
    cost_per_1k_output: float
    speed_tier: str  # "fast", "medium", "slow"
    capability_tier: str  # "reasoning", "coding", "general", "creative"
    supports_json: bool = True
    supports_vision: bool = False
    supports_tools: bool = True
    is_local: bool = False
    max_output_tokens: int = 4096
    avg_latency_ms: float = 1000.0  # Updated dynamically
    success_rate: float = 1.0  # Updated dynamically
    total_calls: int = 0
    total_failures: int = 0

@dataclass
class RoutingDecision:
    model: ModelProfile
    reason: str
    fallback_chain: List[ModelProfile] = field(default_factory=list)

class LLMRouter:
    """
    Intelligent multi-provider LLM router with:
    - Automatic model selection based on task type
    - Fallback chains for reliability
    - Cost optimization
    - Latency tracking and optimization
    - Local model support
    - Response caching
    """



    def __init__(self, config: dict, observability: Any = None):
        self.config = config
        self.observability = observability
        self.models: Dict[str, ModelProfile] = {}
        self.response_cache: Dict[str, dict] = {} # Deprecated in favor of CacheManager
        self.provider_clients: Dict[str, Any] = {}
        
        # Resilience
        self.reliability = ReliabilityManager(config)
        
        # Caching
        self.cache_manager = CacheManager(config)
        
        self._init_providers()
        self._init_models()


    def _init_providers(self):
        """Initialize all configured provider clients."""
        provider_configs = self.config.get("providers", {})
        
        # We will populate this as we implement more providers
        # Starting with the basics needed for testing
        
        # OpenAI
        if provider_configs.get("openai", {}).get("api_key"):
            self.provider_clients["openai"] = {
                "base_url": "https://api.openai.com/v1",
                "api_key": provider_configs["openai"]["api_key"],
                "headers": {
                    "Authorization": f"Bearer {provider_configs['openai']['api_key']}",
                    "Content-Type": "application/json"
                }
            }

        # Ollama (local)
        ollama_url = provider_configs.get("ollama", {}).get("base_url", "http://localhost:11434")
        self.provider_clients["ollama"] = {
            "base_url": ollama_url,
            "api_key": None,
            "headers": {"Content-Type": "application/json"}
        }

    def _init_models(self):
        """Register all available models with their profiles."""
        model_registry = [
            # OpenAI
            ModelProfile(Provider.OPENAI, "gpt-4o", "GPT-4o", 128000, 0.0025, 0.01, "medium", "reasoning", supports_vision=True),
            ModelProfile(Provider.OPENAI, "gpt-4o-mini", "GPT-4o Mini", 128000, 0.00015, 0.0006, "fast", "general", supports_vision=True),
            
            # Local Models (Ollama)
            ModelProfile(Provider.OLLAMA, "llama3.1:8b", "Llama 3.1 8B (Local)", 128000, 0.0, 0.0, "medium", "general", is_local=True),
            ModelProfile(Provider.OLLAMA, "llama3.1:70b", "Llama 3.1 70B (Local)", 128000, 0.0, 0.0, "slow", "reasoning", is_local=True),
        ]

        for model in model_registry:
            # Only register if provider is configured
            provider_name = model.provider.value
            if provider_name in self.provider_clients:
                self.models[f"{provider_name}/{model.model_id}"] = model

    def select_model(self, task_type: str = "general", priority: str = "balanced", require_json: bool = True) -> RoutingDecision:
        """Intelligently select the best model for the task."""
        candidates = list(self.models.values())
        
        # Basic filtering
        if require_json:
            candidates = [m for m in candidates if m.supports_json]
            
        if not candidates:
             raise ValueError("No suitable models found")
             
        # Simple scoring for now (can be expanded)
        # Prioritize local if priority is 'cost'
        if priority == "cost":
             candidates.sort(key=lambda m: (not m.is_local, m.cost_per_1k_input))
        else:
             candidates.sort(key=lambda m: m.success_rate, reverse=True)
             
        best = candidates[0]
        fallbacks = candidates[1:3]
        
        return RoutingDecision(
            model=best,
            reason=f"Selected {best.display_name} for {task_type}",
            fallback_chain=fallbacks
        )

    async def complete(self, messages: List[dict], **kwargs) -> dict:
        """Universal completion method."""
        routing = self.select_model(**kwargs)
        model = routing.model
        start_time = time.time()
        
        # Check Cache
        cached_response = await self.cache_manager.get(
            prompt=str(messages), 
            model_id=model.model_id, 
            **kwargs
        )
        if cached_response:
            if self.observability:
                self.observability.record_metric("llm.cache.hit", 1, {"model": model.model_id})
            return cached_response
            
        async def _execute_request():
            if model.provider == Provider.OPENAI:
                 return await self._call_openai_compatible(model, messages, **kwargs)
            elif model.provider == Provider.OLLAMA:
                 return await self._call_ollama(model, messages, **kwargs)
            else:
                raise NotImplementedError(f"Provider {model.provider} not supported yet")

        try:
            # Use ReliabilityManager to execute the request with resilience
            response = await self.reliability.execute_with_resilience(
                provider=model.provider.value,
                func=_execute_request,
                rate_limit_name=model.provider.value
            )
            
            # Record observability metrics
            if self.observability:
                duration_ms = (time.time() - start_time) * 1000
                usage = response.get("usage", {})
                
                self.observability.cost_tracker.record_cost(
                    provider=model.provider.value,
                    model=model.model_id,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    cost_per_1k_input=model.cost_per_1k_input,
                    cost_per_1k_output=model.cost_per_1k_output,
                    task_type=kwargs.get("task_type", "unknown")
                )
                
                self.observability.performance_tracker.record_response_time(
                    agent=f"llm.{model.provider.value}",
                    action="complete",
                    duration_ms=duration_ms
                )
            
            # Cache the response
            await self.cache_manager.set(
                prompt=str(messages),
                model_id=model.model_id,
                value=response,
                **kwargs
            )
            
            return response

        except Exception as e:
            # Log failure?
            raise e

    async def _call_openai_compatible(self, model, messages, **kwargs):
        client_config = self.provider_clients[model.provider.value]
        payload = {
            "model": model.model_id,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "stream": kwargs.get("stream", False)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{client_config['base_url']}/chat/completions",
                headers=client_config["headers"],
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"API Error: {text}")
                
                if kwargs.get("stream"):
                    return resp.content # Return stream reader
                
                data = await resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "model": model.model_id,
                    "usage": data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
                }

    async def _call_ollama(self, model, messages, **kwargs):
        client_config = self.provider_clients["ollama"]
        payload = {
            "model": model.model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7)
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{client_config['base_url']}/api/chat",
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Ollama Error: {text}")
                data = await resp.json()
                return {
                    "content": data["message"]["content"],
                    "model": model.model_id,
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0)
                    }
                }
