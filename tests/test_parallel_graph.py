
import asyncio
import pytest
import sys
import os
sys.path.append(os.getcwd())

from cortex.graph import graph
from langchain_core.messages import HumanMessage
from cortex.events import EventBus, EventType

@pytest.mark.asyncio
async def test_parallel_routing():
    """
    Verify that the Supervisor routes to multiple agents in parallel
    when presented with a multi-domain task.
    """
    # 1. Setup
    user_input = "Please research the current price of Ethereum and also write a Python script to calculate the gas fees for a transaction."
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "blackboard": {},
        "plan": [],
        "meta_data": {}
    }
    
    # 2. Monitor Events
    event_bus = EventBus.get_sync()
    routing_decisions = []
    
    def on_state_change(event):
        if event.data.get("action") == "routing_decision":
            routing_decisions.append(event.data.get("next_agent"))
            
    event_bus.subscribe(EventType.AGENT_STATE_CHANGE, on_state_change)

    # 3. Execute Graph (Run until first routing decision)
    # We can't easily "pause" the graph, but we can check the first decision event.
    # Running the full graph might take too long if agents actually execute.
    # For this test, we just want to see the Supervisor's decision.
    
    print("\n--- Starting Parallel Routing Test ---")
    try:
        async for event in graph.astream(initial_state):
            for node, state in event.items():
                print(f"Node executed: {node}")
                if node == "Supervisor":
                    # Supervisor has run. Check routing.
                    # We expect the next step to be determined by now.
                    # The event bus should have caught it.
                    pass
            
            # Break early if we see parallel execution starting
            # In LangGraph, parallel nodes run in the same step or subsequent steps depending on config.
            # If we see Researcher AND Coder, success.
            if "Researcher" in event or "Coder" in event:
                print("Worker agents started.")
                break

    except Exception as e:
        print(f"Graph execution error: {e}")

    # 4. Assertions
    print(f"\nRouting Decisions: {routing_decisions}")
    
    # Check if we got a list or multiple routing events
    parallel_triggered = False
    for decision in routing_decisions:
        if isinstance(decision, list) and len(decision) > 1:
            if "Researcher" in decision and "Coder" in decision:
                parallel_triggered = True
                
    assert parallel_triggered, f"Supervisor did not trigger parallel agents. Decisions: {routing_decisions}"

if __name__ == "__main__":
    asyncio.run(test_parallel_routing())
