from app.agents.base import BaseAgent
from app.core.orchestrator import AgentContext
from app.models.content_models import MultiPlatformContent
from app.services.openrouter_generator import generate_platform_content


class CopywritingAgent(BaseAgent):
    """
    Omni-Channel Copywriting Agent.
    Transforms UTD into structured layout variants for every target platform.
    """

    def __init__(self):
        super().__init__(name="copywriting_agent")

    async def execute(self, ctx: AgentContext) -> AgentContext:
        if not ctx.unified_truth_document:
            raise ValueError("No Unified Truth Document available for copywriting.")

        content: MultiPlatformContent = await generate_platform_content(
            utd=ctx.unified_truth_document,
            brand_voice=ctx.brand_voice,
        )
        ctx.generated_content = content.model_dump()
        return ctx
