import asyncio
import os
import shutil
from core.coordinator import CoordinatorAgent

async def test_evolution():
    config = {
        "providers": {
            "openai": {"api_key": "test"}
        }
    }
    coordinator = CoordinatorAgent(config)
    
    print("--- Testing Autonomous Evolution ---")
    
    # Mock LLM response for the self-coder
    async def mock_llm_coder(messages, **kwargs):
        # If it's the self-coder prompt
        if "OMNIOS SELF-CODER" in str(messages):
            return {"content": "def automated_code_auditor():\n    \"\"\"Audits code for bugs.\"\"\"\n    return 'Clean'\n\nname = 'automated_code_auditor'\ndescription = 'Analyzes code for stability'"}
        return {"content": "{}"}
        
    coordinator.llm.complete = mock_llm_coder
    
    # Trigger evolution
    await coordinator.evolve()
    
    # Check if file was created
    expected_path = "c:/Users/cw_21/Desktop/Agentic_PoC/agent_fabric/dynamic_tools/auto_automated_code_auditor.py"
    if os.path.exists(expected_path):
        print(f"PASS: Autonomous tool created at {expected_path}")
        # Verify content briefly
        with open(expected_path, "r") as f:
            content = f.read()
            if "def automated_code_auditor" in content:
                print("PASS: Tool content looks correct")
            else:
                print("FAIL: Tool content is mangled")
    else:
        print(f"FAIL: Autonomous tool not found at {expected_path}")

    # Cleanup (keep it for a second to show the user if they look, but usually we'd delete)
    # os.remove(expected_path)

if __name__ == "__main__":
    asyncio.run(test_evolution())
