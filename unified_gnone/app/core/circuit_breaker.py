"""
GNONE — Circuit Breaker Pattern.
Fault isolation for external API calls and service dependencies.
"""

import time
import logging
from enum import Enum
from typing import Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Prevents cascading failures by isolating failing services.
    Transitions: CLOSED -> OPEN (after failures) -> HALF_OPEN (after timeout) -> CLOSED (on success).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def _should_trip(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return self.failure_count >= self.failure_threshold
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("CircuitBreaker '%s': transitioning to HALF_OPEN", self.name)
                return False
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.debug("CircuitBreaker '%s': success recorded, state=CLOSED", self.name)

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning("CircuitBreaker '%s': OPEN after %d failures", self.name, self.failure_count)

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        if self._should_trip():
            raise RuntimeError(f"CircuitBreaker '{self.name}' is OPEN. Service unavailable.")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an async function through the circuit breaker."""
        if self._should_trip():
            raise RuntimeError(f"CircuitBreaker '{self.name}' is OPEN. Service unavailable.")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise


# Pre-configured breakers for key services
gemini_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0, name="gemini_api")
openrouter_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0, name="openrouter_api")
stripe_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="stripe_api")
database_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=10.0, name="database")
