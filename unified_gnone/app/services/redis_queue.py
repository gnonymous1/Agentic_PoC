"""
GNONE — Redis Task Queue Service.
Background job processing for async DAG execution and scheduled tasks.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RedisQueue:
    """Redis-backed task queue for background job processing."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self.redis_url, decode_responses=True)
                logger.info("Redis connection established")
            except ImportError:
                logger.warning("Redis not installed. Using in-memory fallback.")
                self._client = "fallback"
                self._fallback_queue = []
        return self._client

    async def enqueue(self, queue_name: str, task: Dict[str, Any]) -> bool:
        """Add a task to the queue."""
        client = self._get_client()
        task["enqueued_at"] = datetime.utcnow().isoformat()

        if client == "fallback":
            self._fallback_queue.append({"queue": queue_name, "task": task})
            logger.info("Task enqueued (in-memory): %s", queue_name)
            return True

        try:
            await client.rpush(queue_name, json.dumps(task))
            logger.info("Task enqueued in Redis: %s", queue_name)
            return True
        except Exception as exc:
            logger.error("Redis enqueue failed: %s", exc)
            return False

    async def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve and remove the next task from the queue."""
        client = self._get_client()

        if client == "fallback":
            for i, item in enumerate(self._fallback_queue):
                if item["queue"] == queue_name:
                    task = self._fallback_queue.pop(i)
                    return task["task"]
            return None

        try:
            result = await client.lpop(queue_name)
            if result:
                return json.loads(result)
            return None
        except Exception as exc:
            logger.error("Redis dequeue failed: %s", exc)
            return None

    async def peek(self, queue_name: str, count: int = 10) -> list:
        """View tasks in queue without removing them."""
        client = self._get_client()

        if client == "fallback":
            return [item["task"] for item in self._fallback_queue if item["queue"] == queue_name][:count]

        try:
            results = await client.lrange(queue_name, 0, count - 1)
            return [json.loads(r) for r in results]
        except Exception as exc:
            logger.error("Redis peek failed: %s", exc)
            return []

    async def queue_length(self, queue_name: str) -> int:
        """Get the number of tasks in a queue."""
        client = self._get_client()

        if client == "fallback":
            return len([i for i in self._fallback_queue if i["queue"] == queue_name])

        try:
            return await client.llen(queue_name)
        except Exception:
            return 0


# Singleton instance
redis_queue = RedisQueue()
