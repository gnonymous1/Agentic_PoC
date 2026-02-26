import time
import asyncio
import logging
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps

logger = logging.getLogger("omnios.resilience")

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing if service recovered

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    """
    Prevents cascading failures by stopping requests to a failing service.
    """
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0  # To close half-open

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise e

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2: # Require 2 consecutive successes to close
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self, error: Exception):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(f"Circuit {self.name} failure #{self.failure_count}: {error}")

        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()

    def _transition_to_open(self):
        self.state = CircuitState.OPEN
        logger.error(f"Circuit {self.name} OPENED")

    def _transition_to_half_open(self):
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info(f"Circuit {self.name} HALF-OPEN - Testing recovery")

    def _transition_to_closed(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit {self.name} CLOSED - Recovered")


class RateLimiter:
    """
    Simple Token Bucket Rate Limiter (Async).
    """
    def __init__(self, rate: int, period: float = 60.0):
        self.rate = rate
        self.period = period
        self.tokens = rate
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.last_update = now
            
            # Refill tokens
            new_tokens = time_passed * (self.rate / self.period)
            self.tokens = min(self.rate, self.tokens + new_tokens)
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            else:
                wait_time = (1 - self.tokens) / (self.rate / self.period)
                logger.warning(f"Rate limit hit. Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
                return True

class RetryWithBackoff:
    """Advanced retry with exponential backoff and jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,),
        non_retryable_exceptions: tuple = (CircuitBreakerOpenException,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.non_retryable_exceptions = non_retryable_exceptions

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        import random

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.non_retryable_exceptions:
                raise
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    if self.jitter:
                        delay *= random.uniform(0.5, 1.5)
                    logger.warning(f"Retry {attempt+1}/{self.max_retries} after error: {e}. Sleeping {delay:.2f}s")
                    await asyncio.sleep(delay)

        raise last_exception

def retry_with_backoff(retries: int = 3, backoff_in_seconds: float = 1.0):
    """
    Decorator for async functions to retry failures with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_logic = RetryWithBackoff(max_retries=retries, base_delay=backoff_in_seconds)
            return await retry_logic.execute(func, *args, **kwargs)
        return wrapper
    return decorator

class TaskQueue:
    """Priority task queue with dead letter queue."""

    def __init__(self, max_size: int = 1000):
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        self.dead_letter_queue: list = []
        self.processing: Dict[str, dict] = {}
        self.completed: list = []

    async def enqueue(
        self,
        task_id: str,
        task: dict,
        priority: int = 5
    ):
        """Add task to queue. Lower priority number = higher priority."""
        await self.queue.put((priority, time.time(), task_id, task))

    async def dequeue(self) -> tuple:
        """Get next task from queue."""
        priority, timestamp, task_id, task = await self.queue.get()
        self.processing[task_id] = {
            "task": task,
            "started": time.time(),
            "priority": priority
        }
        return task_id, task

    def complete(self, task_id: str, result: dict):
        if task_id in self.processing:
            entry = self.processing.pop(task_id)
            entry["result"] = result
            entry["completed"] = time.time()
            entry["duration"] = entry["completed"] - entry["started"]
            self.completed.append(entry)

    def fail(self, task_id: str, error: str, max_retries: int = 3):
        if task_id in self.processing:
            entry = self.processing.pop(task_id)
            retry_count = entry.get("retries", 0) + 1

            if retry_count <= max_retries:
                entry["retries"] = retry_count
                entry["last_error"] = error
                # Re-enqueue with lower priority
                asyncio.create_task(
                    self.enqueue(
                        task_id, entry["task"],
                        entry["priority"] + 1
                    )
                )
            else:
                entry["final_error"] = error
                self.dead_letter_queue.append(entry)

    def get_status(self) -> dict:
        return {
            "queued": self.queue.qsize(),
            "processing": len(self.processing),
            "completed": len(self.completed),
            "dead_letter": len(self.dead_letter_queue),
        }

class ReliabilityManager:
    """Centralized reliability management."""

    def __init__(self, config: dict):
        self.config = config
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.task_queue = TaskQueue()
        self.retry = RetryWithBackoff(
            max_retries=config.get("max_retries", 3),
            base_delay=config.get("retry_base_delay", 1.0),
        )

        # Initialize circuit breakers for each provider
        providers = config.get("providers", {})
        for provider in providers:
            self.circuit_breakers[provider] = CircuitBreaker(
                name=provider,
                failure_threshold=config.get("circuit_breaker_threshold", 5),
                recovery_timeout=config.get("circuit_breaker_recovery", 60),
            )

        # Initialize rate limiters
        rate_limits = config.get("rate_limits", {
            "openai": {"rate": 50, "period": 60},
            "ollama": {"rate": 100, "period": 60}
        })
        for name, limits in rate_limits.items():
            self.rate_limiters[name] = RateLimiter(
                rate=limits.get("rate", 60),
                period=limits.get("period", 60),
            )

    async def execute_with_resilience(
        self,
        provider: str,
        func: Callable,
        *args,
        rate_limit_name: str = None,
        **kwargs
    ) -> Any:
        """Execute any operation with full resilience stack."""

        # 1. Rate limiting
        rl_name = rate_limit_name or provider
        if rl_name in self.rate_limiters:
            await self.rate_limiters[rl_name].acquire()

        # 2. Circuit breaker
        cb = self.circuit_breakers.get(provider)
        if cb:
            # 3. Retry with backoff (inside circuit breaker)
            return await cb.call(
                self.retry.execute,
                func, *args, **kwargs
            )

        return await self.retry.execute(func, *args, **kwargs)

    def get_health_report(self) -> dict:
        return {
            "circuit_breakers": {
                name: {
                    "state": cb.state.value,
                    "failures": cb.failure_count,
                }
                for name, cb in self.circuit_breakers.items()
            },
            "task_queue": self.task_queue.get_status(),
            "rate_limiters": {
                name: {"tokens": rl.tokens}
                for name, rl in self.rate_limiters.items()
            },
        }
