import pytest
import asyncio
import os
import json
from unittest.mock import MagicMock, patch

# Add project root to path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.synthesis import synthesize_task, execute_synthesis_plan, get_plan_status
from hippocampus.memory import Hippocampus
from cortex.self_evolution import propose_modification, get_modification_history, analyze_code

# Mock LLM to avoid real API calls during test
@pytest.fixture
def setup_mocks():
    # Mock LLM instance
    llm_instance = MagicMock()

    # Mock response for synthesis
    synthesis_response = MagicMock()
    synthesis_response.content = json.dumps({
        "task_analysis": "Research France capital and density",
        "subtasks": [
            {
                "id": 1,
                "description": "Find capital of France",
                "agent": "Researcher",
                "tool": "vector_search",
                "params": {"query": "Capital of France"}
            },
            {
                "id": 2,
                "description": "Calculate density",
                "agent": "Coder",
                "tool": "multiply", # Simplified for test
                "params": {"a": 20000, "b": 1}, # Dummy params
                "depends_on": [1]
            }
        ],
        "risk_assessment": {
            "overall_score": 0.1,
            "risk_factors": {},
            "severity": "low",
            "mitigations": [],
            "confidence": 0.9
        }
    })

    llm_instance.invoke.return_value = synthesis_response

    # Patch the global synthesis_model.llm
    from cortex.synthesis import synthesis_model
    original_llm = synthesis_model.llm
    synthesis_model.llm = llm_instance

    yield

    # Restore
    synthesis_model.llm = original_llm

@pytest.mark.asyncio
async def test_integrated_system_lifecycle(setup_mocks):
    print("\n[TEST] Starting Integrated System Lifecycle Test")

    # 1. Synthesis Phase
    print("[TEST] 1. Synthesis Phase")
    user_request = "Research the capital of France and calculate population density"
    plan = synthesize_task(user_request)

    assert plan is not None
    assert "subtasks" in plan
    assert len(plan["subtasks"]) == 2
    assert "risk_assessment" in plan
    print(f"[TEST] Plan Generated: {len(plan['subtasks'])} tasks, Risk Score: {plan['risk_assessment']['overall_score']}")

    # 2. Execution Phase
    print("[TEST] 2. Execution Phase")
    # Pydantic models (like StructuredTool) are strict about attribute setting/patching.
    # We will patch the tool objects in the synthesis.py module where they are imported
    # BUT dynamic import happens inside the function.
    # So we must patch the tool objects in the source module `agent_fabric.tools`.
    # However, since they are Pydantic objects, `patch.object` on a method might fail if the method is not in __dict__.
    # The safest way is to wrap the tool's `invoke` method manually or mock the tool in `ALL_TOOLS`.

    from agent_fabric.tools import ALL_TOOLS

    # Create mocks
    mock_search_tool = MagicMock()
    mock_search_tool.name = "vector_search"
    mock_search_tool.invoke.return_value = "Paris is the capital of France."

    mock_multiply_tool = MagicMock()
    mock_multiply_tool.name = "multiply"
    mock_multiply_tool.invoke.return_value = 20000

    # Replace in ALL_TOOLS temporarily
    original_tools = list(ALL_TOOLS)

    # Filter out originals and add mocks
    new_tools = [t for t in ALL_TOOLS if t.name not in ["vector_search", "multiply"]]
    new_tools.append(mock_search_tool)
    new_tools.append(mock_multiply_tool)

    # Patch ALL_TOOLS in agent_fabric.tools
    with patch('agent_fabric.tools.ALL_TOOLS', new_tools):
        result = await execute_synthesis_plan(plan)

        assert result["status"] == "completed"
        assert result["completed_tasks"] == 2
        assert result["failed_tasks"] == 0

        # Verify tool calls
        mock_search_tool.invoke.assert_called()
        mock_multiply_tool.invoke.assert_called()
        print("[TEST] Execution Completed Successfully")

        # 3. Reflection Phase (Implicit in execution)
        print("[TEST] 3. Reflection Phase")
        assert "reflection" in result
        reflection = result["reflection"]
        assert "analysis" in reflection
        print(f"[TEST] Reflection Generated: {reflection['insights']}")

    # 4. Memory Phase
    print("[TEST] 4. Memory Phase")
    memory = Hippocampus()
    memory.remember("Paris is the capital of France", {"source": "test_execution"}, layer="knowledge")

    # Verify memory stats (new endpoint logic)
    stats = memory.get_summary()
    assert stats is not None
    assert "total_memories" in stats
    print(f"[TEST] Memory Stats: {stats['total_memories']} total memories")

    # 5. Evolution Phase
    print("[TEST] 5. Evolution Phase")
    # Create a dummy file for analysis
    dummy_file = "dummy_test_file.py"
    with open(dummy_file, "w") as f:
        f.write("def hello():\n    print('Hello')\n")

    try:
        # Analyze
        analysis = analyze_code(dummy_file)
        assert len(analysis.functions) == 1
        assert analysis.functions[0]["name"] == "hello"

        # Propose Modification
        mod = propose_modification(dummy_file, "Add a docstring to hello function")
        assert mod is not None
        assert mod.file_path == dummy_file

        # Check History
        history = get_modification_history()
        assert len(history) > 0
        print(f"[TEST] Evolution History: {len(history)} modifications")

    finally:
        if os.path.exists(dummy_file):
            os.remove(dummy_file)

    print("[TEST] Integrated System Test Completed Successfully")

if __name__ == "__main__":
    # Run with python directly
    import asyncio
    try:
        asyncio.run(test_integrated_system_lifecycle(None)) # mock_llm needs pytest fixture magic, simpler to run via pytest
    except Exception as e:
        print(f"Please run with pytest: {e}")
