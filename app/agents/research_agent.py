from app.agents.base import BaseAgent
from app.core.orchestrator import AgentContext
from app.models.agent_contracts import ResearchContract
from app.services.gemini_grounding import research_topic


class ResearchAgent(BaseAgent):
    """
    Research and Grounding Agent.
    Ingest raw seeds, browse the web using Google Search grounding,
    strip tracking scripts, output a Unified Truth Document.
    """

    def __init__(self):
        super().__init__(name="research_agent")

    async def execute(self, ctx: AgentContext) -> AgentContext:
        utd = await research_topic(ctx.topic, ctx.brand_voice)

        contract = ResearchContract(
            topic=ctx.topic,
            unified_truth_document=utd,
        )
        ctx.unified_truth_document = contract.unified_truth_document
        ctx.source_domains = contract.source_domains
        return ctx
