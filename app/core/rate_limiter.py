import asyncio
import time
from dataclasses import dataclass

from app.core.errors import ModelRateLimitError


@dataclass
class TokenBucket:
    """
    Token bucket rate limiter per model/service.
    Implements the generic cell rate algorithm for precise rate enforcement.
    """
    capacity: int
    refill_rate: float
    refill_interval: float = 1.0

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            await asyncio.sleep(0.05)
        return False

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self.capacity),
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_refill = now


class RateLimiterRegistry:
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def register(self, name: str, capacity: int, refill_rate: float):
        self._buckets[name] = TokenBucket(capacity=capacity, refill_rate=refill_rate)

    async def acquire(self, name: str, tokens: int = 1) -> None:
        bucket = self._buckets.get(name)
        if bucket is None:
            return
        acquired = await bucket.acquire(tokens)
        if not acquired:
            raise ModelRateLimitError(name)

    def get_bucket(self, name: str) -> TokenBucket:
        return self._buckets.get(name)


rate_limiter = RateLimiterRegistry()
