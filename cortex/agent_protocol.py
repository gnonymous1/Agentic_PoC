from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import time
import uuid

class MessageType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    INFORM = "INFORM"
    PROPOSE = "PROPOSE"
    REJECT = "REJECT"
    ACCEPT = "ACCEPT"
    DELEGATE = "DELEGATE"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    DEBATE_TOPIC = "DEBATE_TOPIC"
    DEBATE_ARGUMENT = "DEBATE_ARGUMENT"
    DEBATE_CRITIQUE = "DEBATE_CRITIQUE"
    DEBATE_VERDICT = "DEBATE_VERDICT"
    ERROR = "ERROR"

class AgentMessage(BaseModel):
    """
    Standard message format for inter-agent communication.
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Dict[str, Any]
    conversation_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
