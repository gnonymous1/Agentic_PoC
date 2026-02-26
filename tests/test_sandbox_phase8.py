import asyncio
import os
from agents.dynamic_tool_agent import DynamicToolAgent

async def test_security_sandbox():
    config = {"providers": {"openai": {"api_key": "test"}}}
    dt_agent = DynamicToolAgent(config, "secure_worker")
    
    # Target function that prints to stdout (dangerous tools might do this or more)
    def risky_tool(text: str):
        print(f"I am printing: {text}")
        return len(text)
    
    # In a real test, this function would be loaded by ToolLoader
    # Here we manually wrap it to test the sandbox integration
    wrapped = dt_agent._wrap_tool(risky_tool)
    
    print("--- Testing Sandbox Stdout Capture ---")
    res = await wrapped({"text": "Hello World"})
    print(f"Result: {res}")
    
    if res["status"] == "success" and "I am printing" in res["stdout"]:
        print("PASS: Stdout successfully captured in sandbox")
    else:
        print("FAIL: Stdout capture failed")

    print("\n--- Testing Sandbox Error Isolation ---")
    def crashing_tool(x):
        return x / 0
    
    wrapped_crash = dt_agent._wrap_tool(crashing_tool)
    res_crash = await wrapped_crash({"x": 10})
    print(f"Crash Result: {res_crash}")
    
    if res_crash["status"] == "error" and "division by zero" in res_crash["message"]:
        print("PASS: Exception isolated in sandbox")
    else:
        print("FAIL: Exception not properly handled")

if __name__ == "__main__":
    asyncio.run(test_security_sandbox())
