"""
GNONE — Critic Agent.
Nemotron-3 Super adversarial quality control with self-healing feedback.
"""

import os
import json
import logging
from typing import Dict, Any, Tuple

import httpx

from app.agents.base import BaseAgent
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)

CRITIC_PROMPT = """Check content for:
1. Banned AI words (delve, testament, revolutionizing, moreover, groundbreaking, game-changer, leverage, synergy, cutting-edge)
2. Twitter <=240 chars per post, 5-10 posts
3. LinkedIn: analytical tone, bullet points
4. Blogspot: valid HTML5, min 300 words
5. Brand voice consistency
Return ONLY: {"approved": true/false, "refinement_notes": "specific defects"}"""


class CriticAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "critic_agent"

    @property
    def description(self) -> str:
        return "Adversarial QA and self-healing feedback via Nemotron-3"

    async def execute(self, draft: dict, **kwargs) -> Dict[str, Any]:
        logger.info("CriticAgent: Evaluating content")

        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gnone.local",
            "X-Title": "GNONE Critic",
        }

        payload = {
            "model": "nvidia/nemotron-3-super",
            "messages": [{"role": "system", "content": CRITIC_PROMPT}, {"role": "user", "content": f"Critique:\n{json.dumps(draft, indent=2)}"}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        await limiter.acquire("openrouter")

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
        approved = bool(parsed.get("approved", False))
        notes = str(parsed.get("refinement_notes", ""))

        if not approved:
            approved, notes = self._heuristic_check(draft)

        return {"approved": approved, "refinement_notes": notes, "status": "success" if approved else "rejected"}

    def _heuristic_check(self, draft: dict) -> Tuple[bool, str]:
        banned = ["delve", "testament", "revolutionizing", "moreover", "groundbreaking", "game-changer", "leverage", "synergy", "cutting-edge"]
        failures = []

        twitter = draft.get("twitter", {})
        posts = twitter.get("posts", [])
        if not (5 <= len(posts) <= 10):
            failures.append("Twitter thread must be 5-10 posts")
        for i, post in enumerate(posts):
            if len(post) > 240:
                failures.append(f"Tweet {i+1} exceeds 240 chars")
            for word in banned:
                if word in post.lower():
                    failures.append(f"Tweet {i+1} has banned word '{word}'")

        blogspot = draft.get("blogspot", {})
        html_body = blogspot.get("html_body", "")
        if len(html_body.split()) < 300:
            failures.append("Blogspot below minimum length")

        if failures:
            return False, "DEFECTS: " + "; ".join(failures)
        return True, "Heuristic pass"
