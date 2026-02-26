import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.events import EventBus, EventType
from cortex.registry import registry
from cortex.agent_protocol import MessageType

# Mock LLM to avoid API key requirements
sys.modules['cortex.llm'] = MagicMock()
sys.modules['cortex.llm'].get_llm = MagicMock(return_value=MagicMock())

# Now import BaseAgent after mocking
from agent_fabric.agent import BaseAgent

async def test_agent_collaboration():
    print(">>> Starting Phase 5 Collaboration Test")
    
    # 1. Initialize EventBus
    bus = await EventBus.get()
    
    # 2. Create Agents
    print(">>> Creating Agents...")
    agent_a = BaseAgent(name="Agent Alpha", system_prompt="You are Agent Alpha.", role="researcher")
    agent_b = BaseAgent(name="Agent Beta", system_prompt="You are Agent Beta.", role="analyst")
    
    # 3. Verify Registry
    print(">>> Verifying Registry...")
    agents = registry.list_all_agents()
    print(f"Registered Agents: {[a.name for a in agents]}")
    
    assert len(agents) == 2
    assert registry.get_agent("agent_alpha") is not None
    assert registry.get_agent("agent_beta") is not None
    print("Registry verification passed.")
    
    # 4. Test Messaging
    print(">>> Testing Messaging (Alpha -> Beta)...")
    content = {"task": "analyze_data", "data": [1, 2, 3]}
    
    await agent_a.send_message(
        receiver_id="agent_beta",
        content=content,
        msg_type=MessageType.REQUEST
    )
    
    # Allow some time for event processing
    await asyncio.sleep(0.1)
    
    # 5. Verify Receipt
    print(f">>> Checking Agent Beta's Inbox (Size: {len(agent_b.inbox)})...")
    if len(agent_b.inbox) > 0:
        msg = agent_b.inbox[0]
        print(f"Received Message: {msg}")
        assert msg.sender_id == "agent_alpha"
        assert msg.content == content
        assert msg.message_type == MessageType.REQUEST
        print("Messaging verification passed.")
    else:
        print("Agent Beta did not receive the message.")
        # Debug: Check event history
        history = bus.get_history(EventType.AGENT_MESSAGE)
        print(f"Event Bus History ({len(history)} events):")
        for e in history:
            print(f"- {e.type}: {e.data}")
            
    # 6. Test Broadcast
    print(">>> Testing Broadcast (Beta -> All)...")
    await agent_b.send_message(
        receiver_id="broadcast",
        content={"status": "online"},
        msg_type=MessageType.INFORM
    )
    
    await asyncio.sleep(0.1)
    
    # Alpha should receive it
    if len(agent_a.inbox) > 0:
        print("Agent Alpha received broadcast.")
    else:
        print("Agent Alpha missed broadcast.")

    print(">>> Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_agent_collaboration())
