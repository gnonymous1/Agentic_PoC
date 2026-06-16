"""
GNONE — Copywriting Agent.
DeepSeek-v4 Flash via OpenRouter for multi-platform content generation.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.models.schemas import MultiPlatformPayload
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)

COPYWRITING_PROMPT = """Transform the UTD into structured corporate content. Output ONLY valid JSON:
{"twitter": {"posts": ["..."]}, "linkedin": {"body": "...", "hashtags": ["#Tag"]}, "blogspot": {"title": "...", "html_body": "..."}}
Twitter: 5-10 posts, each <=240 chars. LinkedIn: analytical with metrics. Blogspot: semantic HTML5, min 600 words.
BANNED: delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge."""


class CopywritingAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "copywriting_agent"

    @property
    def description(self) -> str:
        return "Multi-platform content generation via DeepSeek-v4"

    async def execute(self, utd: str, persona_prompt: str = "", critic_feedback: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        logger.info("CopywritingAgent: Generating drafts")

        user_msg = f"UTD:\n\n{utd}\n\nPersona: {persona_prompt}"
        if critic_feedback:
            user_msg += f"\n\nFEEDBACK:\n{critic_feedback}\nFix all errors."

        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Copywriter",
        }

        payload = {
            "model": "deepseek/deepseek-v4-flash:free",
            "messages": [{"role": "system", "content": COPYWRITING_PROMPT}, {"role": "user", "content": user_msg}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }

        await limiter.acquire("openrouter")

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
        draft = MultiPlatformPayload.model_validate(parsed)
        return {"payload": draft.model_dump(), "status": "success"}
