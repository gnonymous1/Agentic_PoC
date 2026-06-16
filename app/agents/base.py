from app.core.orchestrator import AgentContext
from app.core.orchestrator import BaseAgent as CoreBaseAgent


class BaseAgent(CoreBaseAgent):
    """Concrete base agent that all GNONE agents inherit from."""

    async def execute(self, ctx: AgentContext) -> AgentContext:
        raise NotImplementedError
