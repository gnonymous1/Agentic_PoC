import asyncio
import time
from dataclasses import dataclass
from enum import Enum

from app.core.errors import CircuitBreakerOpen


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_retries: int = 3


class CircuitBreaker:
    """
    Resilient circuit breaker pattern for upstream API dependencies.
    Prevents cascading failures by short-circuiting calls to degraded services.
    """

    def __init__(self, service_name: str, config: CircuitBreakerConfig = None):
        self.service = service_name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_attempts = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro_factory):
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                    self._half_open_probe_succeeded = False
                else:
                    raise CircuitBreakerOpen(self.service)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probe_succeeded or self._half_open_attempts >= self.config.half_open_max_retries:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                else:
                    self._half_open_attempts += 1

        try:
            result = coro_factory()
            if hasattr(result, '__await__'):
                result = await result
        except Exception:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
            raise

        async with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED

        return result

    def reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0


class CircuitBreakerManager:
    """
    Manages per-model circuit breakers with fallback chain support.
    """
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._fallbacks: dict[str, list[str]] = {}

    def register(self, name: str, breaker: CircuitBreaker):
        self._breakers[name] = breaker

    def register_fallback_chain(self, primary: str, fallbacks: list[str]):
        self._fallbacks[primary] = fallbacks

    def get(self, name: str) -> CircuitBreaker:
        return self._breakers[name]

    async def call_with_fallback(self, name: str, coro_factory, fallback_factories: dict[str, callable] = None):
        breaker = self._breakers.get(name)
        if breaker and breaker.state == CircuitState.OPEN:
            chain = [name] + self._fallbacks.get(name, [])
            last_error = None
            for model in chain:
                fb_breaker = self._breakers.get(model)
                if fb_breaker and fb_breaker.state == CircuitState.OPEN:
                    last_error = CircuitBreakerOpen(model)
                    continue
                try:
                    factory = coro_factory
                    if fallback_factories and model != name and model in fallback_factories:
                        factory = fallback_factories[model]
                    if fb_breaker:
                        return await fb_breaker.call(factory)
                    return await factory()
                except Exception as e:
                    last_error = e
                    continue
            raise last_error

        if breaker:
            return await breaker.call(coro_factory)
        return await coro_factory()


breaker_manager = CircuitBreakerManager()
