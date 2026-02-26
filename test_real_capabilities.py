import asyncio
import os
from agent_fabric.tools import execute_python, consolidate_memory

async def test_real_execution():
    print("Testing Real Python Execution...")
    code = """
import os
with open('test_output.txt', 'w') as f:
    f.write('Hello from real execution!')
print('Execution success')
"""
    result = execute_python.invoke(code)
    print(f"Execution Result: {result}")
    
    # Verify file creation
    if os.path.exists('test_output.txt'):
        with open('test_output.txt', 'r') as f:
            content = f.read()
        print(f"File Content: {content}")
        if content == 'Hello from real execution!':
            print("PASS: File write execution verified")
            os.remove('test_output.txt')
        else:
            print("FAIL: Content mismatch")
    else:
        print("FAIL: File not created")

async def test_memory_consolidation():
    print("\nTesting Memory Consolidation...")
    # Add some dummy memories first (if possible via the tool usage, but here we test the tool directly)
    # The tool relies on internal memory state. We assume some state exists or handles empty.
    result = consolidate_memory.invoke({})
    print(f"Consolidation Result: {result}")
    if "Consolidation result:" in result:
        print("PASS: Consolidation tool returns structure")
    else:
        print("FAIL: Unexpected consolidation output")

async def main():
    await test_real_execution()
    await test_memory_consolidation()

if __name__ == "__main__":
    asyncio.run(main())
