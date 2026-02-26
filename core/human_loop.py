import asyncio
import uuid
from enum import Enum
from typing import Dict, Any, Optional, Callable, List

class InteractionType(Enum):
    APPROVAL = "approval"
    CLARIFICATION = "clarification"

class InteractionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESPONDED = "responded"

class HumanInteractionManager:
    """
    Manages asynchronous human-in-the-loop interactions.
    Handles approval gates and requests for clarification.
    """

    def __init__(self):
        self.active_interactions: Dict[str, dict] = {}

    async def request_approval(self, operation: str, context: dict) -> str:
        """Create an approval request and return its ID."""
        interaction_id = str(uuid.uuid4())
        self.active_interactions[interaction_id] = {
            "type": InteractionType.APPROVAL,
            "status": InteractionStatus.PENDING,
            "operation": operation,
            "context": context,
            "future": asyncio.get_event_loop().create_future()
        }
        return interaction_id

    async def request_clarification(self, query: str) -> str:
        """Create a clarification request and return its ID."""
        interaction_id = str(uuid.uuid4())
        print(f"[HUMAN] Registering clarification: {interaction_id}")
        self.active_interactions[interaction_id] = {
            "type": InteractionType.CLARIFICATION,
            "status": InteractionStatus.PENDING,
            "query": query,
            "future": asyncio.get_event_loop().create_future()
        }
        return interaction_id

    async def wait_for_response(self, interaction_id: str) -> Any:
        """Wait for the human to respond to a specific interaction."""
        if interaction_id not in self.active_interactions:
            raise Exception("Interaction ID not found")
        
        return await self.active_interactions[interaction_id]["future"]

    def submit_response(self, interaction_id: str, response: Any):
        """Submit a human response to an active interaction."""
        if interaction_id not in self.active_interactions:
            return False
        
        interaction = self.active_interactions[interaction_id]
        interaction["status"] = InteractionStatus.RESPONDED
        
        if not interaction["future"].done():
            interaction["future"].set_result(response)
        
        return True

    def get_pending_tasks(self) -> List[dict]:
        """Return all interactions currently awaiting human input."""
        return [
            {"id": k, "type": v["type"].value, "data": v}
            for k, v in self.active_interactions.items()
            if v["status"] == InteractionStatus.PENDING
        ]
