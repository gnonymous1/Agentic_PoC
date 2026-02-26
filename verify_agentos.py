
import os
import sys

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from cortex.graph import graph
from langchain_core.messages import HumanMessage
import time

def test_agent_os():
    print("--- Testing AgentOS ---")
    
    # Test 1: Surfer
    print("\n[TEST 1] Testing Surfer (Web)...")
    print("User: Open google.com and read the page.")
    initial_state = {"messages": [HumanMessage(content="Open https://www.google.com and read the page.")]}
    
    try:
        for event in graph.stream(initial_state):
            for key, value in event.items():
                print(f"> Node: {key}")
                if "messages" in value and value["messages"]:
                    last_msg = value['messages'][-1]
                    content = getattr(last_msg, 'content', str(last_msg))
                    print(f"  Response: {content[:200]}...")
    except Exception as e:
        print(f"Surfer Test Failed: {e}")

    # Test 2: Operator
    print("\n[TEST 2] Testing Operator (OS)...")
    print("User: Take a screenshot of the current screen.")
    initial_state = {"messages": [HumanMessage(content="Take a screenshot of the current screen to verify where we are.")]}
    
    try:
        for event in graph.stream(initial_state):
            for key, value in event.items():
                print(f"> Node: {key}")
                if "messages" in value and value["messages"]:
                    last_msg = value['messages'][-1]
                    content = getattr(last_msg, 'content', str(last_msg))
                    print(f"  Response: {content[:200]}...")
    except Exception as e:
        print(f"Operator Test Failed: {e}")

if __name__ == "__main__":
    test_agent_os()
