import pytest

from app.core.orchestrator import AgentContext, BaseAgent, DAGOrchestrator


class SimpleAgent(BaseAgent):
    def __init__(self, name: str, fail: bool = False):
        super().__init__(name)
        self._fail = fail

    async def execute(self, ctx: AgentContext) -> AgentContext:
        if self._fail:
            raise ValueError(f"Agent '{self.name}' failed intentionally")
        ctx.set(self.name, f"{self.name}_done")
        return ctx


@pytest.mark.asyncio
async def test_single_agent_pipeline():
    orchestrator = DAGOrchestrator()
    orchestrator.register(SimpleAgent("agent_a"))
    ctx = await orchestrator.run(AgentContext(topic="test"))
    assert ctx.get("agent_a") == "agent_a_done"


@pytest.mark.asyncio
async def test_sequential_dag():
    orchestrator = DAGOrchestrator()
    orchestrator.register(SimpleAgent("agent_a"))
    orchestrator.register(SimpleAgent("agent_b"), depends_on=["agent_a"])
    ctx = await orchestrator.run(AgentContext(topic="test"))
    assert ctx.get("agent_a") == "agent_a_done"
    assert ctx.get("agent_b") == "agent_b_done"


@pytest.mark.asyncio
async def test_upstream_failure_skips_downstream():
    orchestrator = DAGOrchestrator()
    orchestrator.register(SimpleAgent("agent_a", fail=True))
    orchestrator.register(SimpleAgent("agent_b"), depends_on=["agent_a"])
    with pytest.raises(ValueError):
        await orchestrator.run(AgentContext(topic="test"))


@pytest.mark.asyncio
async def test_retry_on_failure():
    class FlakyAgent(BaseAgent):
        def __init__(self):
            super().__init__("flaky")
            self._attempts = 0

        async def execute(self, ctx: AgentContext) -> AgentContext:
            self._attempts += 1
            if self._attempts < 2:
                raise ValueError("Flaky")
            return ctx

    orchestrator = DAGOrchestrator()
    orchestrator.register(FlakyAgent())
    ctx = await orchestrator.run(AgentContext(topic="test"))
    assert ctx.get("flaky") is None  # no setter called, but no exception
