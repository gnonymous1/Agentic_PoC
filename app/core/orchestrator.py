import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from graphlib import TopologicalSorter
from typing import Any
from uuid import uuid4

from app.config import settings as app_settings

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    HEALING = "healing"


@dataclass
class AgentContext:
    """Strongly typed context passed between agents in the DAG pipeline."""
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    topic: str = ""
    unified_truth_document: str = ""
    generated_content: dict = field(default_factory=dict)
    critic_approved: bool = False
    refinement_cycles: int = 0
    refinement_notes: str = ""
    brand_voice: str = ""
    errors: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def set(self, key: str, value: Any):
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.metadata[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, self.metadata.get(key, default))


@dataclass
class AgentNode:
    name: str
    dependencies: list[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.PENDING
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2


class BaseAgent(ABC):
    """Abstract base for all GNONE agents with contract enforcement."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, ctx: AgentContext) -> AgentContext:
        ...

    async def run(self, ctx: AgentContext) -> AgentContext:
        self.logger.info("Agent '%s' starting | correlation_id=%s", self.name, ctx.correlation_id)
        try:
            result = await self.execute(ctx)
            self.logger.info("Agent '%s' completed successfully", self.name)
            return result
        except Exception as e:
            self.logger.error("Agent '%s' failed: %s", self.name, str(e), exc_info=True)
            ctx.errors.append({
                "agent": self.name,
                "error": str(e),
                "correlation_id": ctx.correlation_id,
            })
            raise


class DAGOrchestrator:
    """
    Directed Acyclic Graph orchestrator for multi-agent execution.
    Resolves dependency chains using topological sort and executes
    agents concurrently when possible.
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
        self._nodes: dict[str, AgentNode] = {}
        self._graph: dict[str, list[str]] = {}

    def register(self, agent: BaseAgent, depends_on: list[str] | None = None):
        self._agents[agent.name] = agent
        self._nodes[agent.name] = AgentNode(name=agent.name, dependencies=depends_on or [])
        self._graph[agent.name] = depends_on or []

    def _build_execution_plan(self) -> list[list[str]]:
        ts = TopologicalSorter(self._graph)
        return list(ts.static_order())

    async def run(self, ctx: AgentContext | None = None, timeout: int | None = None) -> AgentContext:
        ctx = ctx or AgentContext()
        timeout = timeout or app_settings.agent_timeout_seconds
        plan = self._build_execution_plan()

        for agent_name in plan:
            if agent_name not in self._agents:
                continue
            node = self._nodes[agent_name]

            if any(
                self._nodes[dep].status == AgentStatus.FAILED
                for dep in node.dependencies
            ):
                node.status = AgentStatus.SKIPPED
                self._agents[agent_name].logger.warning(
                    "Skipping '%s' due to upstream failure", agent_name
                )
                continue

            node.status = AgentStatus.RUNNING
            agent = self._agents[agent_name]

            for attempt in range(1, node.max_retries + 1):
                try:
                    ctx = await asyncio.wait_for(agent.run(ctx), timeout=timeout)
                    node.status = AgentStatus.SUCCEEDED
                    break
                except TimeoutError:
                    node.retry_count = attempt
                    if attempt < node.max_retries:
                        node.status = AgentStatus.HEALING
                        self._agents[agent_name].logger.warning(
                            "Timeout on '%s' attempt %d/%d, retrying",
                            agent_name, attempt + 1, node.max_retries
                        )
                        await asyncio.sleep(2.0 * attempt)
                    else:
                        node.status = AgentStatus.FAILED
                        node.error = "Agent timed out"
                        raise
                except Exception as e:
                    node.retry_count = attempt
                    if attempt < node.max_retries:
                        node.status = AgentStatus.HEALING
                        self._agents[agent_name].logger.warning(
                            "Retrying '%s' attempt %d/%d", agent_name, attempt + 1, node.max_retries
                        )
                        await asyncio.sleep(2.0 * attempt)
                    else:
                        node.status = AgentStatus.FAILED
                        node.error = str(e)
                        raise

        return ctx
