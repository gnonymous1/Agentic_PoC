"""
GNONE — Unified Content Engine (RAIG Pipeline).
Research -> Copywriting -> Critic -> Self-Healing Loop.
"""

import os
import json
import logging
from typing import Tuple, Optional

import httpx
from pydantic import ValidationError

from app.models.schemas import MultiPlatformPayload

logger = logging.getLogger(__name__)

# ===========================================================================
# PROMPTS
# ===========================================================================

RESEARCH_SYSTEM_PROMPT = """You are the GNONE Research and Grounding Agent.
1. Search and verify facts using real-time search grounding.
2. Strip internet junk, clickbait, and fluff.
3. Output a comprehensive plain-text Unified Truth Document (UTD) with verified data, inline source citations, and [UNVERIFIED] labels for unconfirmed claims.
Format: Plain text only. No markdown fences. Cite sources inline with [domain.com]. Minimum 400 words."""

COPYWRITING_SYSTEM_PROMPT = """You are the GNONE Omni-Channel Copywriting Agent.
Transform the Unified Truth Document (UTD) into structured corporate content.

Output ONLY a valid JSON object:
{
  "twitter": {"posts": ["Post 1 (<=240 chars)", ...]},
  "linkedin": {"body": "Analytical post with metrics and bullet points", "hashtags": ["#Tag"]},
  "blogspot": {"title": "SEO Title", "html_body": "<h2>...</h2><p>...</p> (min 600 words, semantic HTML5)"}
}

RULES:
1. Twitter: 5-10 posts, each <=240 characters
2. LinkedIn: Deep corporate analysis with metrics, bullet points (•)
3. Blogspot: Semantic HTML5 with <h2>, <h3>, <strong>, lists. Min 600 words
4. BANNED words: delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge
5. All claims must match UTD facts exactly. No hallucination."""

CRITIC_SYSTEM_PROMPT = """You are the GNONE Asymmetric Critic Alignment Filter.
Check content for:
1. Banned AI words (delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge)
2. Twitter length limits (each post <=240 chars)
3. Twitter thread size (5-10 posts)
4. LinkedIn layout (spacing, analytical tone, bullet points)
5. Blogspot HTML5 validation (semantic markup, min 300 words)
6. Corporate brand voice consistency

Return ONLY JSON: {"approved": true/false, "refinement_notes": "specific defects and fix instructions"}"""


class ContentFactoryEngine:
    """RAIG pipeline: Research -> Copywriting -> Critic -> Self-Healing."""

    def __init__(self, gemini_key: str, openrouter_key: str):
        self.gemini_key = gemini_key
        self.openrouter_key = openrouter_key
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

    async def execute_web_research(self, topic: str, persona_prompt: str) -> str:
        """Node B: Gemini 3.1 Flash Lite with Google Search grounding."""
        logger.info("RAIG Node B: Researching '%s'", topic)

        payload = {
            "systemInstruction": {"parts": [{"text": RESEARCH_SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"Research: {topic}\nPersona: {persona_prompt}"}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "text/plain"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.gemini_url}?key={self.gemini_key}", json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            utd = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("RAIG Node B: UTD synthesized (%d chars)", len(utd))
            return utd.strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini research response parse failed: {exc}")

    async def generate_draft(self, utd: str, persona_prompt: str, critic_feedback: Optional[str] = None) -> MultiPlatformPayload:
        """Node C: DeepSeek-v4 Flash via OpenRouter."""
        logger.info("RAIG Node C: Generating platform drafts")

        user_msg = f"UTD:\n\n{utd}\n\nPersona: {persona_prompt}"
        if critic_feedback:
            user_msg += f"\n\nCRITICAL FEEDBACK:\n{critic_feedback}\nFix every error above."

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Copywriter",
        }

        payload = {
            "model": "deepseek/deepseek-v4-flash:free",
            "messages": [{"role": "system", "content": COPYWRITING_SYSTEM_PROMPT}, {"role": "user", "content": user_msg}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(self.openrouter_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            return MultiPlatformPayload.model_validate(parsed)
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            logger.error("Copywriting validation failed: %s", exc)
            raise RuntimeError(f"Draft generation failed: {exc}")

    async def evaluate_with_critic(self, draft: MultiPlatformPayload) -> Tuple[bool, str]:
        """Node D: Nemotron-3 Super via OpenRouter."""
        logger.info("RAIG Node D: Critic evaluation")

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Critic",
        }

        payload = {
            "model": "nvidia/nemotron-3-super",
            "messages": [{"role": "system", "content": CRITIC_SYSTEM_PROMPT}, {"role": "user", "content": f"Critique:\n{json.dumps(draft.model_dump(), indent=2)}"}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.openrouter_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            return bool(parsed.get("approved", False)), str(parsed.get("refinement_notes", ""))
        except (KeyError, IndexError, json.JSONDecodeError):
            logger.warning("Critic API decode failed, using heuristic fallback")
            return self._heuristic_check(draft)

    def _heuristic_check(self, draft: MultiPlatformPayload) -> Tuple[bool, str]:
        """Local heuristic validation fallback."""
        banned = ["delve", "testament", "revolutionizing", "moreover", "groundbreaking", "game-changer", "leverage", "synergy", "cutting-edge"]
        failures = []

        if not (5 <= len(draft.twitter.posts) <= 10):
            failures.append("Twitter thread must be 5-10 posts")
        for i, post in enumerate(draft.twitter.posts):
            if len(post) > 240:
                failures.append(f"Tweet {i+1} exceeds 240 chars")
            for word in banned:
                if word in post.lower():
                    failures.append(f"Tweet {i+1} contains banned word '{word}'")

        corpus = (draft.linkedin.body + draft.blogspot.html_body).lower()
        for word in banned:
            if word in corpus:
                failures.append(f"Body contains banned word: '{word}'")

        if len(draft.blogspot.html_body.split()) < 300:
            failures.append("Blogspot body below minimum length")

        if failures:
            return False, "HEURISTIC DEFECTS: " + "; ".join(failures)
        return True, "Heuristic pass"

    async def execute_publishing_pipeline(self, topic: str, persona_prompt: str, max_healing_turns: int = 3) -> Tuple[MultiPlatformPayload, str, bool]:
        """Full RAIG DAG: Research -> Copywriting -> Critic Loop -> Self-Healing."""
        utd = await self.execute_web_research(topic, persona_prompt)

        critic_feedback = None
        current_draft = None
        approved = False

        for turn in range(1, max_healing_turns + 1):
            logger.info("RAIG Pipeline: Turn %d/%d", turn, max_healing_turns)
            current_draft = await self.generate_draft(utd, persona_prompt, critic_feedback)
            approved, critic_feedback = await self.evaluate_with_critic(current_draft)
            if approved:
                logger.info("Critic PASSED on turn %d", turn)
                break
            logger.warning("Critic FAILED turn %d: %s", turn, critic_feedback)

        if not approved:
            logger.error("Failed to heal content after %d turns", max_healing_turns)

        return current_draft, utd, approved
