import pytest

from app.core.errors import ModelRateLimitError
from app.core.rate_limiter import RateLimiterRegistry, TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_capacity():
    bucket = TokenBucket(capacity=5, refill_rate=10)
    for _ in range(5):
        assert await bucket.acquire(1, timeout=0.5)
    assert not await bucket.acquire(1, timeout=0.1)


@pytest.mark.asyncio
async def test_token_bucket_refill():
    bucket = TokenBucket(capacity=10, refill_rate=100)
    for _ in range(10):
        await bucket.acquire(1, timeout=0.1)
    # Should refill quickly due to high refill rate
    assert await bucket.acquire(1, timeout=0.2)


@pytest.mark.asyncio
async def test_rate_limiter_registry():
    registry = RateLimiterRegistry()
    registry.register("gemini", capacity=5, refill_rate=0.01)
    for _ in range(5):
        await registry.acquire("gemini")
    with pytest.raises(ModelRateLimitError):
        await registry.acquire("gemini")
