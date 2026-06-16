"""
GNONE — Base Agent Abstract Class.
All agents inherit from this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """Abstract base for all GNONE agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Agent capability description."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's primary function."""
        ...

    async def validate_input(self, **kwargs) -> bool:
        """Validate input parameters before execution."""
        return True
