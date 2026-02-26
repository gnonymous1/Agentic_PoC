import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class SubAgentTask:
    name: str
    handler: callable
    description: str
    capabilities: List[str]

class BaseAgent(ABC):
    """
    Base class for all specialist agents.
    Supports sub-agents, inter-agent communication,
    and health monitoring.
    """

    def __init__(self, config: dict, name: str):
        self.config = config
        self.name = name
        self.llm = None  # Set by coordinator
        self.message_bus = None  # Set by coordinator
        self.sub_agents: Dict[str, SubAgentTask] = {}
        self.execution_count = 0
        self.error_count = 0
        self.is_healthy = True
        self._register_sub_agents()

    @abstractmethod
    def _register_sub_agents(self):
        """Register all sub-agents/skills for this agent."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of actions this agent can perform."""
        pass

    def set_llm_router(self, llm):
        self.llm = llm

    def set_message_bus(self, bus: asyncio.Queue):
        self.message_bus = bus

    async def execute(self, action: str, params: dict) -> dict:
        """Execute an action, routing to appropriate sub-agent."""
        self.execution_count += 1

        # Check if action maps to a sub-agent
        for sub_name, sub_agent in self.sub_agents.items():
            if action in sub_agent.capabilities:
                try:
                    result = await sub_agent.handler(params)
                    return result
                except Exception as e:
                    self.error_count += 1
                    raise e

        # Fall back to direct action handling in main agent class
        # Look for methods named action_{action_name}
        handler = getattr(self, f"action_{action}", None)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(params)
                else:
                    return handler(params)
            except Exception as e:
                self.error_count += 1
                raise e

        raise ValueError(
            f"Agent '{self.name}' has no action '{action}'. "
            f"Available: {self.get_capabilities()}"
        )

    async def health_check(self) -> dict:
        return {
            "status": "healthy" if self.is_healthy else "unhealthy",
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "error_rate": (
                self.error_count / max(self.execution_count, 1)
            ),
            "sub_agents": list(self.sub_agents.keys()),
        }
