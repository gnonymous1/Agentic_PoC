
import sys
import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.append(os.getcwd())

# --- 1. Mock critical external dependencies BEFORE imports ---
mock_pyautogui = MagicMock()
sys.modules["pyautogui"] = mock_pyautogui
sys.modules["pygetwindow"] = MagicMock()
sys.modules["pyscreeze"] = MagicMock()
sys.modules["pytweening"] = MagicMock()
sys.modules["mouseinfo"] = MagicMock()
sys.modules["python3-Xlib"] = MagicMock()
sys.modules["winreg"] = MagicMock()

# Mock transformers (sentence-transformers)
sys.modules["sentence_transformers"] = MagicMock()

# Mock playwright
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()

# Mock cortex.llm BEFORE importing cortex.graph
mock_llm_module = MagicMock()
mock_llm_instance = AsyncMock()
mock_llm_module.get_llm.return_value = mock_llm_instance
sys.modules["cortex.llm"] = mock_llm_module

# --- 2. Import the module under test ---
from cortex import graph as graph_module
from cortex.events import EventBus, EventType
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_supervisor_parallel_routing():
    """
    Verifies that the Supervisor node correctly routes to multiple agents
    when the LLM returns a list of agents (simulating parallel execution).
    """

    # Setup
    user_input = "Research the current price of Ethereum and also write a Python script to calculate the gas fees for a transaction."
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "blackboard": {},
        "plan": [],
        "meta_data": {}
    }

    # We patch ChatPromptTemplate in cortex.graph because that's where supervisor_node looks it up.
    with patch("cortex.graph.ChatPromptTemplate") as MockPrompt:
        # Mock the prompt object
        mock_prompt_instance = MagicMock()
        MockPrompt.from_messages.return_value = mock_prompt_instance

        # Mock the chain created by `prompt | llm`
        mock_chain = AsyncMock()
        # Mock the response content from the chain
        mock_chain_response = MagicMock()
        mock_chain_response.content = '{"next": ["Researcher", "Coder"]}'
        mock_chain.ainvoke.return_value = mock_chain_response

        # Make `prompt | llm` return `mock_chain`
        mock_prompt_instance.__or__.return_value = mock_chain

        # Also, prevent actual execution of worker nodes by patching them in the graph module
        with patch("cortex.graph.researcher") as mock_researcher, \
             patch("cortex.graph.coder") as mock_coder:

            mock_researcher.invoke = AsyncMock(return_value={"messages": [HumanMessage(content="Researched info")]})
            mock_coder.invoke = AsyncMock(return_value={"messages": [HumanMessage(content="Coded script")]})

            # Verify that emit_sync was called with the correct event
            # We patch emit_sync on the EventBus instance returned by get_sync()
            # or better, patch the class method or the instance method if we can access the singleton.

            # EventBus.get_sync() returns the singleton.
            bus = EventBus.get_sync()

            with patch.object(bus, 'emit_sync') as mock_emit_sync:
                # Execute ONLY the Supervisor node logic directly to verify routing logic
                # `supervisor_node` expects a state.
                result = await graph_module.supervisor_node(initial_state)

                # Verify result metadata
                assert result["meta_data"]["next"] == ["Researcher", "Coder"]

                # Verify emit_sync call
                # emit_sync(EventType.AGENT_STATE_CHANGE, { ... }, source="supervisor")
                assert mock_emit_sync.called
                args, kwargs = mock_emit_sync.call_args

                # args[0] is event_type, args[1] is data
                assert args[0] == EventType.AGENT_STATE_CHANGE
                data = args[1]
                assert data["action"] == "routing_decision"
                assert data["next_agent"] == ["Researcher", "Coder"]

            print("\nSuccessfully verified Supervisor parallel routing logic!")

if __name__ == "__main__":
    asyncio.run(test_supervisor_parallel_routing())
