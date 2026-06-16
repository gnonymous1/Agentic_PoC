from dataclasses import dataclass
from uuid import uuid4


class RateLimitExceeded(Exception):
    def __init__(self, service: str = "", retry_after: float = 0.0):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for {service}, retry after {retry_after}s")


class ModelTimeoutError(Exception):
    def __init__(self, message: str = ""):
        super().__init__(message)


class TokenBudgetExceeded(Exception):
    def __init__(self, message: str = ""):
        super().__init__(message)


class GNONEBaseError(Exception):
    """Base exception for all GNONE system errors with correlation ID tracking."""

    def __init__(self, message: str, correlation_id: str | None = None):
        self.correlation_id = correlation_id or str(uuid4())
        super().__init__(f"[{self.correlation_id}] {message}")


class AgentContractViolation(GNONEBaseError):
    """Raised when an agent produces output that fails Pydantic schema validation."""

    def __init__(self, agent_name: str, field: str, detail: str):
        super().__init__(
            message=f"Agent '{agent_name}' violated contract on field '{field}': {detail}"
        )
        self.agent_name = agent_name
        self.field = field


class ModelTimeoutError(GNONEBaseError):
    """Raised when an upstream model API call exceeds its configured timeout."""


class ModelRateLimitError(GNONEBaseError):
    """Raised when an upstream API returns 429 or token bucket is empty."""

    def __init__(self, model: str, retry_after: float = 0.0):
        self.retry_after = retry_after
        super().__init__(message=f"Rate limited on model '{model}', retry in {retry_after}s")


class CircuitBreakerOpen(GNONEBaseError):
    """Raised when calling a service whose circuit breaker is tripped."""

    def __init__(self, service: str):
        self.service = service
        super().__init__(message=f"Circuit breaker open for '{service}'")


class OrchestrationError(GNONEBaseError):
    """Raised when the DAG orchestrator encounters a non-recoverable pipeline failure."""


class ContentSafetyViolation(GNONEBaseError):
    """Raised when content violates safety guardrails."""


@dataclass
class ErrorBudget:
    """Tracks error budget consumption per service for SLO compliance."""
    service: str
    total_operations: int = 0
    failed_operations: int = 0
    error_budget_remaining: float = 1.0

    def record_success(self):
        self.total_operations += 1

    def record_failure(self):
        self.total_operations += 1
        self.failed_operations += 1
        self.error_budget_remaining = max(
            0.0,
            1.0 - (self.failed_operations / max(self.total_operations, 1)),
        )

    @property
    def is_exhausted(self) -> bool:
        return self.error_budget_remaining <= 0.0
