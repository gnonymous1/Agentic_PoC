import httpx
from typing import Dict, Any, Tuple
from app.config import settings
from app.core.circuit_breaker import CircuitBreaker, breaker_manager
import logging

logger = logging.getLogger(__name__)

# Register the circuit breaker for Gemini if not already done
if "gemini" not in breaker_manager._breakers:
    breaker_manager.register("gemini", CircuitBreaker("gemini"))

class LLMGatewayService:
    """
    Centralized service for interacting with various LLM providers.
    Initially acts as a passthrough for Gemini, but designed for future
    features like model routing, rate limiting, cost tracking, and caching.
    """
    def __init__(self):
        self._gemini_endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
            f"?key={settings.gemini_api_key}"
        )
        logger.info(f"LLMGatewayService initialized. Gemini endpoint: {self._gemini_endpoint}")

    async def generate_content(self, payload: Dict[str, Any], model_name: str = "gemini") -> Dict[str, Any]:
        """
        Sends a content generation request to the specified LLM.
        Args:
            payload: The API request payload for the LLM.
            model_name: The name of the LLM model to use (e.g., "gemini", "openrouter").
        Returns:
            The JSON response from the LLM API.
        Raises:
            HTTPException if the LLM API returns an error.
        """
        if model_name == "gemini":
            return await self._call_gemini_api(payload)
        # Add logic for other models here in future phases
        else:
            raise ValueError(f"Unsupported LLM model: {model_name}")

    async def _call_gemini_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method to call the Gemini API with circuit breaker."""
        async def _do_request():
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(self._gemini_endpoint, json=payload)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                return response.json()

        try:
            data = await breaker_manager.call_with_fallback("gemini", _do_request)
            return data
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise # Re-raise the exception to be handled by the caller
