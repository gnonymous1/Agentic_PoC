import uuid
from typing import Tuple


from app.config import settings
from app.core.circuit_breaker import CircuitBreaker, breaker_manager
from app.core.prompt_registry import prompt_registry
from app.services.llm_gateway_service import LLMGatewayService

llm_gateway_service = LLMGatewayService()
from app.services.gemini_grounding import _strip_tracking_fluff # Reuse helper

# Register the circuit breaker for Gemini if not already done in gemini_grounding
if "gemini" not in breaker_manager._breakers:
    breaker_manager.register("gemini", CircuitBreaker("gemini"))


# Define the system prompt for the support assistant
SUPPORT_ASSISTANT_SYSTEM_PROMPT = """You are SEPE Support Assistant, an AI-powered chatbot designed to assist users with the Sovereign Executive Proxy Engine (SEPE) platform.

Your primary goal is to provide helpful, concise, and accurate answers to user questions about:
- SEPE features and functionalities (e.g., Clones, HITL, Simulation, Voice Cloning, Dashboard).
- Basic usage instructions and how to navigate the platform.
- Troubleshooting common issues.
- Explaining core concepts like "digital clones," "agent pipeline," "circuit breakers," and "HITL" (Human-In-The-Loop).

Guidelines:
- Be polite, professional, and friendly.
- Do not make up information. If you do not know the answer to a question, politely state that you don't have enough information to provide a precise answer.
- Keep responses concise and to the point.
- Do not engage in casual conversation outside of support queries.
- Do not provide code examples unless specifically asked and it's a direct feature of SEPE.
- Avoid making external API calls or performing actions outside of providing information.
"""

class SupportChatService:
    def __init__(self):
        # Register the support assistant's system prompt
        self._prompt_hash = prompt_registry.register(
            "support_assistant_prompt",
            SUPPORT_ASSISTANT_SYSTEM_PROMPT,
            metadata={"source": __file__, "type": "system_prompt"}
        )
        self._conversation_history = {} # In-memory storage for conversation history

    async def get_chat_response(self, message: str, conversation_id: str | None) -> Tuple[str, str]:
        if not conversation_id or conversation_id not in self._conversation_history:
            conversation_id = str(uuid.uuid4())
            self._conversation_history[conversation_id] = []

        # Retrieve the current active system prompt
        system_instruction_text = prompt_registry.get_active("support_assistant_prompt")

        # Prepare conversation history for Gemini API
        gemini_history = []
        for role, text in self._conversation_history[conversation_id]:
            gemini_history.append({"role": role, "parts": [{"text": text}]})

        # Add the current user message to the history and payload
        gemini_history.append({"role": "user", "parts": [{"text": message}]})

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction_text}]
            },
            "contents": gemini_history,
            "generationConfig": {
                "temperature": settings.gemini_temperature,
                "maxOutputTokens": settings.gemini_max_output_tokens,
                "topP": settings.gemini_top_p,
                "topK": settings.gemini_top_k,
                "responseMimeType": "text/plain",
            },
        }

        data = await llm_gateway_service.generate_content(payload, "gemini")

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned zero candidates for the support request.")

        raw_text = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            raw_text += part.get("text", "")

        cleaned_reply = _strip_tracking_fluff(raw_text)

        # Store the conversation history (user message and Gemini's reply)
        self._conversation_history[conversation_id].append(("user", message))
        self._conversation_history[conversation_id].append(("model", cleaned_reply))

        return cleaned_reply, conversation_id
