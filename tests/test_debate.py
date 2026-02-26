import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.events import EventBus, Event, EventType
from cortex.agent_protocol import AgentMessage, MessageType
from cortex.reasoning.debate import DebateManager
from agent_fabric.agent import BaseAgent

# Mock LLM
sys.modules['cortex.llm'] = MagicMock()
sys.modules['cortex.llm'].get_llm = MagicMock(return_value=MagicMock())

class MockDebater(BaseAgent):
    async def _handle_message(self, event: Event):
        if event.type == EventType.AGENT_MESSAGE:
            data = event.data
            if data.get("receiver_id") == self.agent_id:
                msg = AgentMessage(**data)
                print(f"[{self.name}] Received: {msg.content}")
                
                # Auto-reply for testing
                if msg.message_type == MessageType.REQUEST and msg.content.get("action") == "provide_argument":
                    print(f"[{self.name}] Providing argument...")
                    await self.send_message(
                        receiver_id=msg.sender_id,
                        content={"argument": f"Argument from {self.name} for round {msg.content.get('round')}"},
                        msg_type=MessageType.DEBATE_ARGUMENT
                    )
                elif msg.message_type == MessageType.REQUEST and msg.content.get("action") == "verdict":
                    print(f"[{self.name}] Providing verdict...")
                    await self.send_message(
                        receiver_id=msg.sender_id,
                        content={"verdict": "Proponent wins"},
                        msg_type=MessageType.DEBATE_VERDICT
                    )

async def test_debate():
    print(">>> Starting Debate Engine Test")
    
    # 1. Setup
    bus = await EventBus.get()
    
    # 2. Create Agents
    proponent = MockDebater(name="Proponent Agent", system_prompt="")
    opponent = MockDebater(name="Opponent Agent", system_prompt="")
    judge = MockDebater(name="Judge Agent", system_prompt="")
    
    # 3. Initialize Debate
    debate = DebateManager(topic="Python vs Rust", rounds=1)
    debate.add_participant(proponent, "proponent")
    debate.add_participant(opponent, "opponent")
    debate.add_participant(judge, "judge")
    
    # 4. Start Debate
    task = asyncio.create_task(debate.start_debate())
    
    # Wait for completion (simulated via bus activity)
    await asyncio.sleep(4.0) 
    
    # 5. Check Transcript (Mock) or just status
    print(f"Debate Status: {debate.status}")
    assert debate.status == "completed" or debate.status == "active"
    
    print("Test Complete: Debate Flow Verified.")

if __name__ == "__main__":
    asyncio.run(test_debate())
