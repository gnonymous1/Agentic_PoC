from app.agents.base import BaseAgent
from app.core.orchestrator import AgentContext
from app.models.content_models import MultiPlatformContent
from app.services.critic_loop import MaxRetriesExceededError, critic_verification_loop


class CriticAgent(BaseAgent):
    """
    Asymmetric Critic Agent.
    Cross-examines generated content against brand guardrails and AI fluff hallmarks.
    """

    def __init__(self):
        super().__init__(name="critic_agent")

    async def execute(self, ctx: AgentContext) -> AgentContext:
        if not ctx.generated_content:
            raise ValueError("No generated content to critique.")

        content = MultiPlatformContent.model_validate(ctx.generated_content)

        try:
            approved_content, cycles = await critic_verification_loop(
                generated=content,
                original_utd=ctx.unified_truth_document,
                brand_voice=ctx.brand_voice,
            )
            ctx.critic_approved = True
            ctx.refinement_cycles = cycles
            ctx.generated_content = approved_content.model_dump()
        except MaxRetriesExceededError as e:
            ctx.critic_approved = False
            ctx.refinement_notes = e.last_refinement_notes
            ctx.refinement_cycles = 3
            self.logger.warning(
                "Critic retry budget exhausted for %s", ctx.correlation_id
            )

        return ctx
