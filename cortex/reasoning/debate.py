import asyncio
from typing import List, Dict, Any, Optional
from cortex.agent_protocol import AgentMessage, MessageType
from cortex.registry import registry
from cortex.events import EventBus, EventType
from agent_fabric.agent import BaseAgent
import uuid

class DebateManager:
    def __init__(self, topic: str, rounds: int = 2):
        self.topic = topic
        self.rounds = rounds
        self.participants: Dict[str, str] = {} # agent_id -> role
        self.transcript: List[Dict] = []
        self.conversation_id = str(uuid.uuid4())
        self.bus = EventBus.get_sync()
        self.status = "initializing"

    def add_participant(self, agent: BaseAgent, role: str):
        """Roles: 'proponent', 'opponent', 'judge'"""
        self.participants[agent.agent_id] = role
        print(f"[DebateManager] Added {agent.name} as {role}")

    async def start_debate(self):
        self.status = "active"
        print(f"[DebateManager] Starting debate on: {self.topic}")
        
        # 1. Announce Topic
        for agent_id, role in self.participants.items():
            await self._send_to_agent(agent_id, {
                "action": "start_round", 
                "topic": self.topic,
                "role": role,
                "rounds": self.rounds
            }, MessageType.DEBATE_TOPIC)

        # 2. Run Rounds
        for i in range(1, self.rounds + 1):
            print(f"[DebateManager] --- Round {i} ---")
            await self._conduct_round(i)

        # 3. Request Verdict
        await self._get_verdict()
        self.status = "completed"

    async def _conduct_round(self, round_num: int):
        # Proponent speaks first
        await self._turn("proponent", round_num)
        # Opponent speaks second
        await self._turn("opponent", round_num)

    async def _turn(self, role_type: str, round_num: int):
        # Find agent with this role
        agent_id = next((id for id, r in self.participants.items() if r == role_type), None)
        if not agent_id:
            return

        print(f"[DebateManager] Requesting argument from {role_type} ({agent_id})...")
        
        # Send Request
        await self._send_to_agent(agent_id, {
            "action": "provide_argument",
            "round": round_num,
            "transcript": self.transcript
        }, MessageType.REQUEST)

        # Wait for Response (Mocking wait for async event logic)
        # In a real system, we'd wait for an event. Here we simulate the delay/response flow.
        # For this prototype, we assume the agent replies quickly or we wait a fixed time.
        await asyncio.sleep(1) 
        
        # In a real impl, we would hook into the EventBus and await specific message_id reply.
        # Here we just fetch the last message from agent's outbox (simulated via bus snooping or direct lookup if accessible)
        # Since we can't easily peek into other agents' internal state, let's look at the EventBus history for the reply
        
        # This is strictly a naive wait implementation for the PoC
        await asyncio.sleep(2) 

    async def _get_verdict(self):
        judge_id = next((id for id, r in self.participants.items() if r == "judge"), None)
        if judge_id:
            print(f"[DebateManager] Requesting verdict from Judge ({judge_id})...")
            await self._send_to_agent(judge_id, {
                "action": "verdict",
                "transcript": self.transcript
            }, MessageType.REQUEST)

    async def _send_to_agent(self, agent_id: str, content: Dict, msg_type: MessageType):
        msg = AgentMessage(
            sender_id="debate_manager",
            receiver_id=agent_id,
            message_type=msg_type,
            content=content,
            conversation_id=self.conversation_id
        )
        await self.bus.emit_async(EventType.AGENT_MESSAGE, msg.dict(), source="DebateManager")
