"""
GNONE — Moderator Agent.
Final content approval gate before deployment.
"""

import logging
from typing import Dict, Any

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ModeratorAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "moderator_agent"

    @property
    def description(self) -> str:
        return "Final content moderation and deployment readiness check"

    async def execute(self, payload: dict, critic_approved: bool = False, **kwargs) -> Dict[str, Any]:
        logger.info("ModeratorAgent: Final review")

        if not critic_approved:
            return {"status": "rejected", "reason": "Critic did not approve content"}

        # Validate payload structure
        required = ["twitter", "linkedin", "blogspot"]
        missing = [k for k in required if k not in payload]
        if missing:
            return {"status": "rejected", "reason": f"Missing platforms: {missing}"}

        # Validate twitter posts length
        for i, post in enumerate(payload.get("twitter", {}).get("posts", [])):
            if len(post) > 240:
                return {"status": "rejected", "reason": f"Tweet {i+1} exceeds 240 chars"}

        return {"status": "approved", "ready_for_deployment": True}
