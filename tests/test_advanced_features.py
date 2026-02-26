import pytest
import os
import json
from unittest.mock import MagicMock, patch
from agent_fabric.skills.system.file_ops import list_files_recursive
from agent_fabric.skills.coding.dev_tools import git_clone
from cortex.workflow_registry import WorkflowRegistry, WorkflowGenerator

@pytest.mark.asyncio
async def test_advanced_skills():
    print("\n[TEST] Verifying Advanced Skills")

    # 1. Test File Ops (Real)
    # StructuredTool is not callable directly, need to invoke it properly or access underlying func if available
    # For langchain tools, .invoke() is standard, but simple @tool decorated functions can sometimes be called if not wrapped yet?
    # Actually, @tool wraps it in StructuredTool. To call the logic directly for testing:
    # We can use .invoke(input) or .run(input)

    output = list_files_recursive.invoke({"path": "."})
    assert "tests/" in output
    print("[TEST] list_files_recursive: OK")

    # 2. Test Git (Mock)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        # Git clone tool also needs invoke
        output = git_clone.invoke({"repo_url": "https://github.com/test/repo.git"})
        assert "Successfully cloned" in output
        print("[TEST] git_clone: OK")

@pytest.mark.asyncio
async def test_workflow_library_generation():
    print("\n[TEST] Verifying Workflow Library Generation")

    registry = WorkflowRegistry("tests/data/workflows")
    generator = WorkflowGenerator(registry)

    # Mock LLM for generation
    # Pydantic models (like LangChain LLMs) don't like direct patching of methods if they are not fields.
    # We'll use a wrapper mock instead.

    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "workflows": [
            {
                "id": "generated_01",
                "name": "Gen Flow",
                "description": "Desc",
                "category": "Test",
                "tags": ["test"],
                "steps": [{"agent": "Coder", "tool": "git_clone", "params": {}}]
            }
        ]
    })

    with patch("cortex.workflow_registry.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm_instance

        # Re-init generator with mocked LLM factory
        generator = WorkflowGenerator(registry)

        generator.generate_presets(1)

        # Verify persistence
        wf = registry.get_workflow("generated_01")
        assert wf is not None
        assert wf.name == "Gen Flow"
        print(f"[TEST] Workflow Generation: OK ({wf.name})")

    # Cleanup
    if os.path.exists("tests/data/workflows/generated_01.json"):
        os.remove("tests/data/workflows/generated_01.json")
        os.rmdir("tests/data/workflows")
        os.rmdir("tests/data")

if __name__ == "__main__":
    # Simplified runner
    import asyncio
    asyncio.run(test_advanced_skills())
    asyncio.run(test_workflow_library_generation())
