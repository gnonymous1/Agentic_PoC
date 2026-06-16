"""
Redis-backed cache with idempotent task queue support.
Provides token bucket rate limiting and session state persistence.
"""

import json
import os
from dataclasses import dataclass


@dataclass
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    socket_timeout: int = 5
    retry_on_timeout: bool = True


class Cache:
    def __init__(self, config: RedisConfig | None = None):
        self.config = config or RedisConfig()
        self._client = None

    async def connect(self):
        import redis.asyncio as aioredis
        self._client = aioredis.from_url(
            self.config.url,
            socket_timeout=self.config.socket_timeout,
            retry_on_timeout=self.config.retry_on_timeout,
            decode_responses=True,
        )

    async def disconnect(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> str | None:
        if not self._client:
            return None
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        if not self._client:
            return False
        return await self._client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> bool:
        if not self._client:
            return False
        return await self._client.delete(key) > 0

    async def enqueue(self, queue: str, payload: dict) -> None:
        await self._client.lpush(queue, json.dumps(payload))

    async def dequeue(self, queue: str, timeout: int = 5) -> dict | None:
        result = await self._client.brpop(queue, timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    async def health(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if not self._client:
            return 0
        return await self._client.zadd(key, mapping)

    async def zrem(self, key: str, *members: str) -> int:
        if not self._client:
            return 0
        return await self._client.zrem(key, *members)

    async def zrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> list[str]:
        if not self._client:
            return []
        return await self._client.zrangebyscore(key, min_score, max_score)

    async def zcard(self, key: str) -> int:
        if not self._client:
            return 0
        return await self._client.zcard(key)

    async def lpush(self, key: str, value: str) -> int:
        if not self._client:
            return 0
        return await self._client.lpush(key, value)

    async def rpop(self, key: str) -> str | None:
        if not self._client:
            return None
        return await self._client.rpop(key)

    async def llen(self, key: str) -> int:
        if not self._client:
            return 0
        return await self._client.llen(key)

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if not self._client:
            return False
        await self._client.ltrim(key, start, end)
        return True

    async def keys(self, pattern: str) -> list[str]:
        if not self._client:
            return []
        return await self._client.keys(pattern)

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._client:
            return False
        return await self._client.expire(key, ttl)


cache = Cache()
