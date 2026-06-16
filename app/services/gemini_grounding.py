import re


from app.config import settings
from app.core.circuit_breaker import CircuitBreaker, breaker_manager
from app.services.llm_gateway_service import LLMGatewayService

llm_gateway_service = LLMGatewayService()

SYSTEM_INSTRUCTION = """You are a Research and Grounding Agent operating inside an overnight content manufacturing pipeline.

Your sole purpose is to:
1. Accept a raw topic seed or news snippet from the user.
2. Use the **googleSearch** grounding tool to perform real-time web research — verify facts, pull current statistics, and identify the key narrative angles.
3. Strip out all internet tracking fluff, affiliate-link noise, clickbait headlines, and paywalled filler.
4. Return a single, clean **Unified Truth Document (UTD)** — a factual, well-structured, neutral-toned text summary that a downstream copywriting agent can immediately consume without further fact-checking.

Format rules:
- Output ONLY the Unified Truth Document. No preamble, no commentary, no markdown fences.
- Use plain text paragraphs separated by double newlines.
- Always cite your sources inline in [brackets] with the domain name.
- If a fact cannot be verified across at least 2 independent sources, explicitly mark it as [UNVERIFIED].
- Minimum 400 words. Maximum 2000 words."""


def _strip_tracking_fluff(text: str) -> str:
    patterns = [
        r"https?://[^\s]*?(?:track|click|redirect|affiliate|ref|utm_source)[^\s]*",
        r"\{#[^}]*#\}",
        r"<!--.*?-->",
        r"(?:advertisement|sponsored|promoted|paid partnership).*?(?:\n|$)",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    lines = [l for l in text.split("\n") if l.strip()]
    return "\n\n".join(lines)


async def research_topic(topic: str, brand_voice: str | None = None) -> str:
    user_prompt = f"Research the following topic and produce a Unified Truth Document:\n\n{topic}"
    if brand_voice:
        user_prompt += (
            f"\n\nBrand voice context (integrate where relevant):\n{brand_voice}"
        )

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "tools": [{"googleSearch": {}}],
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
        raise RuntimeError("Gemini returned zero candidates for the research request.")

    raw_text = ""
    for part in candidates[0].get("content", {}).get("parts", []):
        raw_text += part.get("text", "")

    cleaned = _strip_tracking_fluff(raw_text)

    if len(cleaned.split()) < 50:
        raise ValueError(
            f"Gemini returned an undersized UTD ({len(cleaned.split())} words). "
            "Retry with a more specific topic."
        )

    return cleaned
