import re

from app.agents.base import BaseAgent
from app.core.orchestrator import AgentContext
from app.models.agent_contracts import ModeratorVerdict
from app.models.content_models import MultiPlatformContent

FLAGGED_PATTERNS = {
    "hate_speech": r"\b(hate|kill|destroy)\s+(the\s+)?(\w+\s+){0,3}(people|group|race|religion)\b",
    "harassment": r"\b(bully|harass|threaten|intimidate)\b",
    "pii": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "profanity": r"\b(fuck|shit|asshole|bitch|cunt|damn)\b",
}

BRAND_SAFETY_PATTERNS = {
    "competitor_mention": r"\b(competitor|rival|better than)\s+\w+\b",
    "unverified_claim": r"\b(guaranteed|100%|best|number one|#1)\b",
}


class ModeratorAgent(BaseAgent):
    """
    Content Safety Moderator Agent.
    Scans all generated content for PII, hate speech, harassment,
    brand safety violations, and regulatory compliance issues.
    """

    def __init__(self):
        super().__init__(name="moderator_agent")

    async def execute(self, ctx: AgentContext) -> AgentContext:
        content = ctx.generated_content
        if not content:
            return ctx

        all_text = self._flatten_content(content)
        flagged = []

        for category, pattern in {**FLAGGED_PATTERNS, **BRAND_SAFETY_PATTERNS}.items():
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            if matches:
                flagged.append(category)
                self.logger.warning(
                    "Flagged category '%s' in content for %s",
                    category, ctx.correlation_id,
                )

        verdict = ModeratorVerdict(
            passed_safety_check=len(flagged) == 0,
            content_safe=len(flagged) == 0,
            flagged_categories=flagged,
            moderation_notes=f"Flagged {len(flagged)} categories" if flagged else "Passed all checks",
        )

        ctx.set("moderator_verdict", verdict.model_dump())
        return ctx

    def _flatten_content(self, content: dict) -> str:
        parts = []
        try:
            model = MultiPlatformContent.model_validate(content)
            parts.extend(model.twitter.posts)
            parts.append(model.linkedin.body)
            parts.append(model.facebook.body)
            parts.append(model.blogspot.html_body)
        except Exception:
            parts.append(str(content))
        return " ".join(parts)
