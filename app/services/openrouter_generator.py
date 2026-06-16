import asyncio
import json
import logging
import random

import httpx

from app.config import settings
from app.core.circuit_breaker import CircuitBreaker, breaker_manager
from app.core.metrics import requests_total
from app.models.content_models import MultiPlatformContent

logger = logging.getLogger(__name__)

OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {settings.openrouter_api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://gnone.local",
    "X-Title": "GNONE Content Manufacturing Loop",
}

GENERATOR_SYSTEM_PROMPT = """You are an Omni-Channel Copywriting Agent. Your job is to transform a Unified Truth Document (UTD) into structured, platform-native content drafts.

Output *only* a single valid JSON object conforming exactly to the following schema — no markdown fences, no commentary:

{
  "twitter": {
    "posts": [
      "Post 1 text (max 240 chars)...",
      "Post 2 text (max 240 chars)...",
      "... (5 to 10 posts total)"
    ]
  },
  "linkedin": {
    "body": "Professional executive-toned post with line breaks and bullet points...",
    "hashtags": ["#IndustryTag1", "#IndustryTag2"]
  },
  "facebook": {
    "body": "Conversational community-focused post...",
    "call_to_action": "What are your thoughts? Comment below!"
  },
  "blogspot": {
    "title": "SEO-Optimized Title Here",
    "seo_slug": "seo-optimized-title-here",
    "meta_description": "Compelling 320-char meta description...",
    "html_body": "<h2>Section Heading</h2><p>Content with <strong>key phrases</strong>...</p>"
  }
}

RULES:
- Twitter: exactly 5-10 posts, each ≤240 characters. Write an engaging thread, not standalone tweets.
- LinkedIn: professional, executive tone. Use line breaks, bullet points (•), data points from the UTD.
- Facebook: conversational, warm, ends with a CTA question or prompt. No hashtag stuffing.
- Blogspot: comprehensive long-form HTML5. Use <h2> and <h3> for headings, <strong> for SEO keywords, <ul>/<li> for lists. Minimum 600 words of content in html_body.
- NEVER use these fluff words: delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge.
- Fact-check everything against the UTD. Do not hallucinate numbers or quotes."""

breaker_manager.register("openrouter_primary", CircuitBreaker("openrouter_primary"))
breaker_manager.register("openrouter_fallback", CircuitBreaker("openrouter_fallback"))
breaker_manager.register("openrouter_fallback_2", CircuitBreaker("openrouter_fallback_2"))
breaker_manager.register("openrouter_fallback_3", CircuitBreaker("openrouter_fallback_3"))

MAX_429_RETRIES = 5


def _log_usage(data: dict) -> None:
    usage = data.get("usage", {})
    if usage:
        logger.info(
            "Token usage - prompt: %s, completion: %s, total: %s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
        requests_total.labels(
            model=data.get("model", "unknown"),
            status="success",
        ).inc()


async def _call_model(payload: dict, headers: dict, model_label: str) -> dict:
    for attempt in range(1, MAX_429_RETRIES + 1):
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "1")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 1.0
                jitter = random.uniform(0, 0.5)
                logger.warning(
                    "429 on %s (attempt %d/%d), retrying in %.2fs",
                    model_label, attempt, MAX_429_RETRIES, delay + jitter,
                )
                await asyncio.sleep(delay + jitter)
                continue
            response.raise_for_status()
            data = response.json()
            _log_usage(data)
            return data
    raise RuntimeError(f"Exhausted 429 retries for {model_label}")


def _build_payload(model: str, utd: str, brand_voice: str | None) -> dict:
    user_message = f"Unified Truth Document:\n\n{utd}"
    if brand_voice:
        user_message += (
            f"\n\nBrand Voice Instructions (must follow):\n{brand_voice}"
        )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": settings.generator_temperature,
        "max_tokens": settings.generator_max_tokens,
        "response_format": {"type": "json_object"},
    }


_MODEL_CHAIN = [
    ("openrouter_primary", "generator_model"),
    ("openrouter_fallback", "generator_fallback_model"),
    ("openrouter_fallback_2", "generator_fallback_model_2"),
    ("openrouter_fallback_3", "generator_fallback_model_3"),
]


async def generate_platform_content(
    utd: str,
    brand_voice: str | None = None,
) -> MultiPlatformContent:
    payloads = {
        label: _build_payload(getattr(settings, model_field), utd, brand_voice)
        for label, model_field in _MODEL_CHAIN
    }

    async def _try(label: str, p: dict):
        return await _call_model(p, OPENROUTER_HEADERS, label)

    data = None
    for label, _ in _MODEL_CHAIN:
        try:
            data = await breaker_manager.call_with_fallback(label, lambda l=label, p=payloads[label]: _try(l, p))
            break
        except Exception:
            logger.warning("Model %s failed, trying next in chain", label)
            continue

    if data is None:
        raise RuntimeError("All generator models exhausted")

    raw_content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    parsed = json.loads(raw_content)
    return MultiPlatformContent.model_validate(parsed)
