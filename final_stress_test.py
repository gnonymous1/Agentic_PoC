
import os
import sys
import time

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from cortex.graph import graph
from langchain_core.messages import HumanMessage

def run_stress_test():
    print("=== FINAL AGENTOS STRESS TEST ===")
    
    # 1. Test Multimodal Memory & Operator
    print("\n[STRESS 1] Operator Vision & Memory Capture...")
    state1 = {"messages": [HumanMessage(content="Take a screenshot of the current screen and analyze it. Then tell me what you see.")]}
    for event in graph.stream(state1):
        for node, val in event.items():
            print(f"> Node: {node}")
            if "messages" in val and val["messages"]:
                print(f"  Response: {val['messages'][-1].content[:200]}...")

    # 2. Test Dream Layer (Consolidation)
    print("\n[STRESS 2] Running Dream Layer (Consolidation)...")
    state2 = {"messages": [HumanMessage(content="Consolidate our recent activities into high-level knowledge.")]}
    for event in graph.stream(state2):
        for node, val in event.items():
            print(f"> Node: {node}")
            if "messages" in val and val["messages"]:
                print(f"  Response: {val['messages'][-1].content[:200]}...")

    # 3. Test Self-Evolution (Architect creates a tool)
    print("\n[STRESS 3] Self-Evolution Test...")
    tool_code = """
from langchain_core.tools import tool
@tool
def get_system_uptime_mock() -> str:
    \"\"\"Returns a mock system uptime.\"\"\"
    return "System uptime: 124 minutes (Mock)"
"""
    state3 = {"messages": [HumanMessage(content=f"Create a new tool named 'get_system_uptime_mock' that returns a fake uptime. Code: {tool_code}")]}
    for event in graph.stream(state3):
        for node, val in event.items():
            print(f"> Node: {node}")
            if "messages" in val and val["messages"]:
                 print(f"  Response: {val['messages'][-1].content[:200]}...")

    print("\n=== STRESS TEST COMPLETE ===")

if __name__ == "__main__":
    run_stress_test()
