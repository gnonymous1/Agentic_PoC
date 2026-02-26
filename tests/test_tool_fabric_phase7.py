import asyncio
import os
from core.coordinator import CoordinatorAgent
from agents.dynamic_tool_agent import DynamicToolAgent

async def test_platform_expansion():
    config = {
        "providers": {
            "openai": {"api_key": "test"}
        }
    }
    coordinator = CoordinatorAgent(config)
    
    # Register DynamicToolAgent
    dt_agent = DynamicToolAgent(config, "dynamic_worker")
    coordinator.agents["dynamic_worker"] = dt_agent
    coordinator.agent_capabilities["dynamic_worker"] = dt_agent.get_capabilities()
    
    print("--- Testing Dynamic Tool Loading ---")
    caps = dt_agent.get_capabilities()
    print(f"Loaded Capabilities: {caps}")
    
    if "get_current_time" in caps:
        print("PASS: Dynamic tool 'get_current_time' discovered")
    else:
        print("FAIL: Dynamic tool not found")

    print("\n--- Testing Execution of Dynamic Tool ---")
    res = await dt_agent.execute("get_current_time", {"timezone": "EST"})
    print(f"Result: {res}")
    
    if res["status"] == "success" and "time" in res["result"]:
        print("PASS: Dynamic tool executed successfully")
    else:
        print("FAIL: Dynamic tool execution failed")

if __name__ == "__main__":
    asyncio.run(test_platform_expansion())
