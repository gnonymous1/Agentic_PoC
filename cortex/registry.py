from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

class AgentCapability(BaseModel):
    name: str
    description: str
    metadata: Dict = Field(default_factory=dict)

class AgentInfo(BaseModel):
    agent_id: str
    name: str
    role: str
    capabilities: List[AgentCapability] = Field(default_factory=list)
    status: str = "active" # active, busy, offline
    last_seen: float = Field(default_factory=time.time)
    endpoint: Optional[str] = None # For future distributed setup

class AgentRegistry:
    _instance = None
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def register_agent(self, agent_info: AgentInfo):
        """Registers a new agent or updates an existing one."""
        self._agents[agent_info.agent_id] = agent_info
        logger.info(f"Agent registered: {agent_info.name} ({agent_info.agent_id})")
        
    def deregister_agent(self, agent_id: str):
        """Removes an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Agent deregistered: {agent_id}")
            
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Retrieves agent info by ID."""
        return self._agents.get(agent_id)
        
    def find_agents_by_capability(self, capability_name: str) -> List[AgentInfo]:
        """Finds agents that have a specific capability."""
        matches = []
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap.name == capability_name:
                    matches.append(agent)
                    break
        return matches
        
    def find_agents_by_role(self, role: str) -> List[AgentInfo]:
        """Finds agents with a specific role."""
        return [a for a in self._agents.values() if a.role == role]
    
    def heartbeat(self, agent_id: str):
        """Updates the last_seen timestamp for an agent."""
        if agent_id in self._agents:
            self._agents[agent_id].last_seen = time.time()
            self._agents[agent_id].status = "active"

    def list_all_agents(self) -> List[AgentInfo]:
        """Returns a list of all registered agents."""
        return list(self._agents.values())

# Global registry instance
registry = AgentRegistry.get_instance()
