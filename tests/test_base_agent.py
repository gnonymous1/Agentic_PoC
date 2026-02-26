import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from agents.base_agent import BaseAgent, SubAgentTask

class ConcreteAgent(BaseAgent):
    """
    Concrete implementation of BaseAgent for testing purposes.
    """
    def _register_sub_agents(self):
        # Register a mock sub-agent
        self.mock_handler = AsyncMock(return_value={"status": "sub_agent_success"})
        self.sub_agents["sub1"] = SubAgentTask(
            name="sub1",
            handler=self.mock_handler,
            description="A test sub agent",
            capabilities=["test_sub_action"]
        )

        # Register a sub-agent that will fail
        self.fail_handler = AsyncMock(side_effect=ValueError("Sub Agent Error"))
        self.sub_agents["sub_fail"] = SubAgentTask(
            name="sub_fail",
            handler=self.fail_handler,
            description="A failing sub agent",
            capabilities=["test_sub_fail"]
        )

    def get_capabilities(self):
        return [
            "test_sub_action",
            "test_sub_fail",
            "test_direct_action",
            "test_direct_action_async",
            "test_error"
        ]

    def action_test_direct_action(self, params):
        return {"status": "success", "params": params}

    async def action_test_direct_action_async(self, params):
        return {"status": "success_async", "params": params}

    def action_test_error(self, params):
        raise ValueError("Test Error")

@pytest.fixture
def agent():
    config = {"test_config": "value"}
    return ConcreteAgent(config=config, name="test_agent")

def test_initialization(agent):
    assert agent.config == {"test_config": "value"}
    assert agent.name == "test_agent"
    assert agent.execution_count == 0
    assert agent.error_count == 0
    assert agent.is_healthy
    assert "sub1" in agent.sub_agents
    assert "sub_fail" in agent.sub_agents

def test_set_llm_router(agent):
    mock_llm = Mock()
    agent.set_llm_router(mock_llm)
    assert agent.llm == mock_llm

def test_set_message_bus(agent):
    mock_bus = asyncio.Queue()
    agent.set_message_bus(mock_bus)
    assert agent.message_bus == mock_bus

@pytest.mark.asyncio
async def test_execute_sub_agent(agent):
    params = {"key": "value"}
    result = await agent.execute("test_sub_action", params)

    assert result == {"status": "sub_agent_success"}
    assert agent.execution_count == 1
    agent.mock_handler.assert_called_once_with(params)

@pytest.mark.asyncio
async def test_execute_direct_sync(agent):
    params = {"key": "value"}
    result = await agent.execute("test_direct_action", params)

    assert result == {"status": "success", "params": params}
    assert agent.execution_count == 1

@pytest.mark.asyncio
async def test_execute_direct_async(agent):
    params = {"key": "value"}
    result = await agent.execute("test_direct_action_async", params)

    assert result == {"status": "success_async", "params": params}
    assert agent.execution_count == 1

@pytest.mark.asyncio
async def test_execute_unknown_action(agent):
    with pytest.raises(ValueError) as excinfo:
        await agent.execute("unknown_action", {})

    assert "has no action 'unknown_action'" in str(excinfo.value)
    assert agent.execution_count == 1

@pytest.mark.asyncio
async def test_execute_sub_agent_error(agent):
    with pytest.raises(ValueError, match="Sub Agent Error"):
        await agent.execute("test_sub_fail", {})

    assert agent.execution_count == 1
    assert agent.error_count == 1

@pytest.mark.asyncio
async def test_execute_direct_error(agent):
    with pytest.raises(ValueError, match="Test Error"):
        await agent.execute("test_error", {})

    assert agent.execution_count == 1
    assert agent.error_count == 1

@pytest.mark.asyncio
async def test_health_check(agent):
    # Simulate some activity
    await agent.execute("test_direct_action", {}) # success
    try:
        await agent.execute("test_error", {}) # fail
    except ValueError:
        pass

    health = await agent.health_check()

    assert health["status"] == "healthy"
    assert health["execution_count"] == 2
    assert health["error_count"] == 1
    assert health["error_rate"] == 0.5
    assert "sub1" in health["sub_agents"]
