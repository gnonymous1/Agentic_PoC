"""
GNONE — Rate Limiter.
Token bucket rate limiting for API calls and resource access.
"""

import time
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter for a single resource."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        while not self.consume(tokens):
            await asyncio.sleep(1.0 / self.rate)


class RateLimiter:
    """Multi-resource rate limiter."""

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}

    def register(self, name: str, rate: float, capacity: int) -> None:
        self.buckets[name] = TokenBucket(rate, capacity)

    async def acquire(self, name: str, tokens: int = 1) -> None:
        if name not in self.buckets:
            raise KeyError(f"Rate limiter bucket '{name}' not registered")
        await self.buckets[name].wait_for_token(tokens)


# Pre-configured rate limits
limiter = RateLimiter()
limiter.register("gemini", rate=1.0, capacity=10)
limiter.register("openrouter", rate=0.5, capacity=5)
limiter.register("stripe", rate=0.2, capacity=3)
limiter.register("social_api", rate=2.0, capacity=20)
