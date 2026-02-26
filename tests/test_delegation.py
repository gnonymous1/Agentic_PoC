import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.events import EventBus
from cortex.agent_protocol import MessageType
from cortex.specialized_agents import ManagerAgent, ResearcherAgent

# Mock LLM
sys.modules['cortex.llm'] = MagicMock()
mock_llm = MagicMock()
mock_response = MagicMock()
mock_response.content = "Analysis Complete: The data suggests a positive trend."
mock_response.tool_calls = []
mock_llm.ainvoke.return_value = mock_response
sys.modules['cortex.llm'].get_llm = MagicMock(return_value=mock_llm)

async def test_delegation():
    print(">>> Starting Delegation Test")
    
    # 1. Initialize Bus
    bus = await EventBus.get()
    
    # 2. Create Agents
    manager = ManagerAgent(name="Manager")
    researcher = ResearcherAgent(name="Researcher")
    
    print(f"Agents Created: {manager.name}, {researcher.name}")
    
    # 3. Manager Delegates Task
    print(">>> Manager delegating task to Researcher...")
    task = "Analyze Q1 sales data."
    await manager.send_message(
        receiver_id=researcher.agent_id,
        content={"task": task},
        msg_type=MessageType.DELEGATE
    )
    
    # Give time for processing
    await asyncio.sleep(0.5)
    
    # 4. Check Researcher's Inbox
    if len(researcher.inbox) > 0:
        print("Researcher received task.")
    else:
        print("Researcher inbox empty.")
        
    # 5. Check Manager's Inbox for updates
    # Should have ACCEPT and TASK_COMPLETE
    print(f"Manager Inbox Size: {len(manager.inbox)}")
    for msg in manager.inbox:
        if msg.message_type == MessageType.ACCEPT:
             print("Received ACCEPT.")
        elif msg.message_type == MessageType.TASK_COMPLETE:
             print(f"Received RESULT: {msg.content['result']}")
             
    assert any(m.message_type == MessageType.TASK_COMPLETE for m in manager.inbox)
    print("Test Complete: Delegation Successful.")

if __name__ == "__main__":
    asyncio.run(test_delegation())
