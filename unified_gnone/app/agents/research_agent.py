"""
GNONE — Research Agent.
Gemini 3.1 Flash Lite with Google Search grounding for fact verification.
"""

import os
import logging
from typing import Dict, Any

import httpx

from app.agents.base import BaseAgent
from app.core.circuit_breaker import gemini_breaker
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """You are the GNONE Research Agent. Search, verify, and synthesize facts into a clean Unified Truth Document (UTD).
Output plain text only. Cite sources inline [domain.com]. Mark unverified claims as [UNVERIFIED]. Min 400 words."""


class ResearchAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "research_agent"

    @property
    def description(self) -> str:
        return "Grounded fact search and verification via Gemini with Google Search"

    async def execute(self, topic: str, persona_prompt: str = "", **kwargs) -> Dict[str, Any]:
        logger.info("ResearchAgent: Grounding topic '%s'", topic)

        payload = {
            "systemInstruction": {"parts": [{"text": RESEARCH_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"Research: {topic}\nPersona: {persona_prompt}"}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "text/plain"},
        }

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={gemini_key}"

        await limiter.acquire("gemini")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        utd = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("ResearchAgent: UTD synthesized (%d chars)", len(utd))
        return {"unified_truth_document": utd.strip(), "status": "success"}
