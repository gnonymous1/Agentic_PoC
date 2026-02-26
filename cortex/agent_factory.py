"""
Agent Factory - OpenClaw-style recursive agent spawning
Enables parent agents to spawn child agents for parallel task execution
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from agent_fabric.agent import BaseAgent
from cortex.state import AgentState
from utils.logger import setup_logging

logger = setup_logging()


@dataclass
class SpawnedAgent:
    """Represents a spawned child agent"""
    agent_id: str
    name: str
    agent: BaseAgent
    task: str
    parent_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None


class AgentFactory:
    """
    Factory for creating and managing spawned agents
    Enables recursive spawning like OpenClaw's sessions_spawn
    """
    
    def __init__(self, max_workers: int = 5):
        self.agents: Dict[str, SpawnedAgent] = {}
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def create_agent(
        self,
        name: str,
        role: str,
        system_prompt: str,
        tools: List[Any],
        task: str,
        parent_id: Optional[str] = None
    ) -> SpawnedAgent:
        """
        Create a new specialized agent
        
        Args:
            name: Agent name
            role: Agent role (e.g., "thinker", "coder", "auditor")
            system_prompt: System prompt for the agent
            tools: List of tools available to the agent
            task: The task this agent should perform
            parent_id: ID of parent agent (if spawned by another agent)
        
        Returns:
            SpawnedAgent instance
        """
        agent_id = str(uuid.uuid4())[:8]
        
        # Create the BaseAgent
        agent = BaseAgent(
            name=name,
            system_prompt=system_prompt,
            role=role,
            tools=tools
        )
        
        spawned = SpawnedAgent(
            agent_id=agent_id,
            name=name,
            agent=agent,
            task=task,
            parent_id=parent_id
        )
        
        self.agents[agent_id] = spawned
        logger.info(f"[AgentFactory] Created agent {name} (ID: {agent_id}) for task: {task[:50]}...")
        
        return spawned
    
    async def spawn_and_execute(
        self,
        parent_agent_id: Optional[str],
        name: str,
        role: str,
        system_prompt: str,
        tools: List[Any],
        task: str,
        initial_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Spawn a child agent and execute its task
        
        Args:
            parent_agent_id: ID of parent agent
            name: Child agent name
            role: Child agent role
            system_prompt: System prompt
            tools: Available tools
            task: Task description
            initial_state: Initial AgentState
        
        Returns:
            Execution result
        """
        # Create the agent
        spawned = self.create_agent(
            name=name,
            role=role,
            system_prompt=system_prompt,
            tools=tools,
            task=task,
            parent_id=parent_id
        )
        
        # Update state with task
        state = AgentState(
            messages=initial_state.get("messages", []),
            blackboard=initial_state.get("blackboard", {}),
            plan=initial_state.get("plan", []),
            meta_data=initial_state.get("meta_data", {})
        )
        
        # Execute
        spawned.status = "running"
        try:
            logger.info(f"[AgentFactory] Executing agent {spawned.name} (ID: {spawned.agent_id})")
            result = await spawned.agent.invoke(state)
            spawned.result = result
            spawned.status = "completed"
            logger.info(f"[AgentFactory] Agent {spawned.name} completed successfully")
            return {
                "agent_id": spawned.agent_id,
                "name": spawned.name,
                "status": "completed",
                "result": result
            }
        except Exception as e:
            spawned.error = str(e)
            spawned.status = "failed"
            logger.error(f"[AgentFactory] Agent {spawned.name} failed: {e}")
            return {
                "agent_id": spawned.agent_id,
                "name": spawned.name,
                "status": "failed",
                "error": str(e)
            }
    
    async def spawn_parallel(
        self,
        parent_agent_id: Optional[str],
        agent_configs: List[Dict[str, Any]],
        initial_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Spawn multiple agents in parallel
        
        Example:
            configs = [
                {"name": "Architect", "role": "thinker", "task": "Design API"},
                {"name": "Coder", "role": "coder", "task": "Implement API"},
                {"name": "Auditor", "role": "auditor", "task": "Review security"}
            ]
            results = await factory.spawn_parallel(None, configs, state)
        
        Args:
            parent_agent_id: Parent agent ID
            agent_configs: List of agent configurations
            initial_state: Initial state
        
        Returns:
            List of results from all agents
        """
        tasks = []
        for config in agent_configs:
            task = self.spawn_and_execute(
                parent_agent_id=parent_agent_id,
                name=config["name"],
                role=config.get("role", "execution"),
                system_prompt=config.get("system_prompt", f"You are a {config['name']} agent."),
                tools=config.get("tools", []),
                task=config["task"],
                initial_state=initial_state
            )
            tasks.append(task)
        
        # Execute all in parallel
        logger.info(f"[AgentFactory] Spawning {len(tasks)} agents in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[AgentFactory] Agent {i} raised exception: {result}")
                valid_results.append({
                    "agent_id": None,
                    "name": agent_configs[i]["name"],
                    "status": "failed",
                    "error": str(result)
                })
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_agent(self, agent_id: str) -> Optional[SpawnedAgent]:
        """Get a spawned agent by ID"""
        return self.agents.get(agent_id)
    
    def get_children(self, parent_id: str) -> List[SpawnedAgent]:
        """Get all children of a parent agent"""
        return [agent for agent in self.agents.values() if agent.parent_id == parent_id]
    
    def get_status(self, agent_id: str) -> Optional[str]:
        """Get status of an agent"""
        agent = self.agents.get(agent_id)
        return agent.status if agent else None
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all spawned agents"""
        return [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "status": agent.status,
                "parent_id": agent.parent_id,
                "task": agent.task[:50] + "..." if len(agent.task) > 50 else agent.task
            }
            for agent in self.agents.values()
        ]
    
    def cleanup(self, agent_id: str):
        """Remove an agent from the registry"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"[AgentFactory] Cleaned up agent {agent_id}")
    
    def shutdown(self):
        """Shutdown the factory and cleanup resources"""
        self.executor.shutdown(wait=True)
        self.agents.clear()
        logger.info("[AgentFactory] Shutdown complete")


# Global instance
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """Get global agent factory instance"""
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory


# Tool for spawning agents (to be added to tools.py)
async def sessions_spawn(
    parent_context: str,
    agent_configs: List[Dict[str, Any]],
    parallel: bool = True
) -> Dict[str, Any]:
    """
    OpenClaw-style tool to spawn child agents
    
    Args:
        parent_context: Context from parent agent
        agent_configs: List of agent configurations
        parallel: Whether to run in parallel
    
    Returns:
        Results from all spawned agents
    """
    from langchain_core.messages import HumanMessage
    
    factory = get_agent_factory()
    
    initial_state = {
        "messages": [HumanMessage(content=parent_context)],
        "blackboard": {},
        "plan": [],
        "meta_data": {}
    }
    
    if parallel:
        results = await factory.spawn_parallel(None, agent_configs, initial_state)
    else:
        # Sequential execution
        results = []
        for config in agent_configs:
            result = await factory.spawn_and_execute(
                parent_agent_id=None,
                name=config["name"],
                role=config.get("role", "execution"),
                system_prompt=config.get("system_prompt", f"You are a {config['name']} agent."),
                tools=config.get("tools", []),
                task=config["task"],
                initial_state=initial_state
            )
            results.append(result)
    
    return {
        "status": "completed",
        "agents_spawned": len(agent_configs),
        "results": results
    }
