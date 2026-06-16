"""
GNONE — Enhanced Redis Task Queue

Production-grade task queue with:
- Priority queues (high/medium/low)
- Scheduled/delayed job execution
- Job retry with exponential backoff
- Worker pool management
- Queue monitoring endpoints
- Idempotency guarantees with SHA-256 dedup
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from app.infrastructure.cache import cache

logger = logging.getLogger(__name__)


class Priority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"
    DEAD_LETTER = "dead_letter"


@dataclass
class Job:
    id: str
    queue: str
    priority: str
    payload: dict
    status: str
    created_at: str
    scheduled_at: str | None = None
    dedup_key: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: str | None = None
    result: dict | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RetryPolicy:
    BACKOFF_SCHEDULE = [1, 5, 30, 120, 600, 3600, 14400, 43200]

    @classmethod
    def get_delay(cls, retry_count: int, multiplier: float = 2.0) -> int:
        if retry_count < len(cls.BACKOFF_SCHEDULE):
            return int(cls.BACKOFF_SCHEDULE[retry_count] * multiplier)
        return int(cls.BACKOFF_SCHEDULE[-1] * multiplier * (retry_count - len(cls.BACKOFF_SCHEDULE) + 1))


class TaskQueue:
    """
    Production task queue with priority support, scheduling,
    exponential backoff retry, and SHA-256 deduplication.
    """

    DEDUP_TTL = 86400
    JOB_TTL = 604800
    SCHEDULED_CHECK_INTERVAL = 10
    MAX_WORKERS_PER_QUEUE = 4

    _workers: dict[str, list[asyncio.Task]] = {}
    _running: bool = False

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    async def enqueue(
        self,
        queue: str,
        payload: dict,
        priority: Priority = Priority.MEDIUM,
        dedup: bool = True,
        scheduled_at: datetime | None = None,
        max_retries: int = 3,
        idempotency_key: str | None = None,
    ) -> str | None:
        dedup_key = self._compute_dedup_key(queue, payload) if dedup else None

        if dedup_key:
            existing = await cache.get(f"dedup:{dedup_key}")
            if existing:
                logger.debug("Duplicate job rejected: %s", dedup_key)
                return None

        if idempotency_key:
            existing = await cache.get(f"idempotency:{idempotency_key}")
            if existing:
                logger.debug("Idempotent job rejected: %s", idempotency_key)
                return None

        job = Job(
            id=str(uuid4()),
            queue=queue,
            priority=priority.value,
            payload=payload,
            status=JobStatus.SCHEDULED.value if scheduled_at else JobStatus.PENDING.value,
            created_at=datetime.now(UTC).isoformat(),
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
            dedup_key=dedup_key,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
        )

        if scheduled_at:
            await cache.set(
                f"scheduled:{job.id}",
                json.dumps(job.to_dict()),
                ttl=self.JOB_TTL,
            )
            await cache.zadd(
                "scheduled_jobs",
                {job.id: scheduled_at.timestamp()},
            )
            logger.info(
                "Scheduled job %s for %s",
                job.id,
                scheduled_at.isoformat(),
            )
        else:
            priority_queue = f"queue:{queue}:{priority.value}"
            await cache.lpush(priority_queue, json.dumps(job.to_dict()))

            if dedup_key:
                await cache.set(f"dedup:{dedup_key}", job.id, ttl=self.DEDUP_TTL)
            if idempotency_key:
                await cache.set(f"idempotency:{idempotency_key}", job.id, ttl=self.JOB_TTL)

            await cache.set(
                f"job:{job.id}",
                json.dumps(job.to_dict()),
                ttl=self.JOB_TTL,
            )

            logger.info(
                "Enqueued job %s to %s (priority: %s)",
                job.id,
                queue,
                priority.value,
            )

        return job.id

    async def dequeue(self, queue: str, timeout: int = 5) -> Job | None:
        for priority in [Priority.HIGH, Priority.MEDIUM, Priority.LOW]:
            priority_queue = f"queue:{queue}:{priority.value}"
            result = await cache.rpop(priority_queue)
            if result:
                job_data = json.loads(result)
                job = Job.from_dict(job_data)
                job.status = JobStatus.PROCESSING.value
                job.started_at = datetime.now(UTC).isoformat()
                await cache.set(
                    f"job:{job.id}",
                    json.dumps(job.to_dict()),
                    ttl=self.JOB_TTL,
                )
                return job

        return None

    async def complete_job(self, job: Job, result: dict | None = None) -> None:
        job.status = JobStatus.COMPLETED.value
        job.result = result
        job.completed_at = datetime.now(UTC).isoformat()

        await cache.set(
            f"job:{job.id}",
            json.dumps(job.to_dict()),
            ttl=self.JOB_TTL,
        )

        await cache.lpush(f"completed:{job.queue}", json.dumps(job.to_dict()))
        await cache.ltrim(f"completed:{job.queue}", 0, 999)

        if job.dedup_key:
            await cache.delete(f"dedup:{job.dedup_key}")
        if job.idempotency_key:
            await cache.delete(f"idempotency:{job.idempotency_key}")

        logger.info("Job %s completed successfully", job.id)

    async def fail_job(
        self,
        job: Job,
        error: str,
        requeue: bool = True,
    ) -> None:
        job.error = error

        if requeue and job.retry_count < job.max_retries:
            job.retry_count += 1
            delay = RetryPolicy.get_delay(job.retry_count)
            job.status = JobStatus.RETRYING.value
            retry_at = datetime.now(UTC).timestamp() + delay

            await cache.zadd("retry_jobs", {job.id: retry_at})
            await cache.set(
                f"retry:{job.id}",
                json.dumps({"job": job.to_dict(), "delay": delay}),
                ttl=self.JOB_TTL,
            )

            logger.info(
                "Job %s scheduled for retry %d/%d in %ds",
                job.id,
                job.retry_count,
                job.max_retries,
                delay,
            )
        else:
            job.status = JobStatus.DEAD_LETTER.value
            await cache.lpush(
                f"deadletter:{job.queue}",
                json.dumps(job.to_dict()),
            )
            await cache.ltrim(f"deadletter:{job.queue}", 0, 4999)

            logger.warning(
                "Job %s moved to dead letter queue after %d retries",
                job.id,
                job.retry_count,
            )

        await cache.set(
            f"job:{job.id}",
            json.dumps(job.to_dict()),
            ttl=self.JOB_TTL,
        )

    async def process_scheduled_jobs(self) -> int:
        now = time.time()
        due_jobs = await cache.zrangebyscore("scheduled_jobs", 0, now)

        moved = 0
        for job_id in due_jobs:
            job_data = await cache.get(f"scheduled:{job_id}")
            if job_data:
                job = Job.from_dict(json.loads(job_data))
                job.status = JobStatus.PENDING.value
                job.scheduled_at = None

                priority_queue = f"queue:{job.queue}:{job.priority}"
                await cache.lpush(priority_queue, json.dumps(job.to_dict()))
                await cache.set(
                    f"job:{job.id}",
                    json.dumps(job.to_dict()),
                    ttl=self.JOB_TTL,
                )

                await cache.zrem("scheduled_jobs", job_id)
                await cache.delete(f"scheduled:{job.id}")
                moved += 1

        if moved:
            logger.info("Moved %d scheduled jobs to active queues", moved)
        return moved

    async def process_retry_jobs(self) -> int:
        now = time.time()
        due_retries = await cache.zrangebyscore("retry_jobs", 0, now)

        moved = 0
        for job_id in due_retries:
            retry_data = await cache.get(f"retry:{job_id}")
            if retry_data:
                data = json.loads(retry_data)
                job = Job.from_dict(data["job"])
                job.status = JobStatus.PENDING.value

                priority_queue = f"queue:{job.queue}:{job.priority}"
                await cache.lpush(priority_queue, json.dumps(job.to_dict()))
                await cache.set(
                    f"job:{job.id}",
                    json.dumps(job.to_dict()),
                    ttl=self.JOB_TTL,
                )

                await cache.zrem("retry_jobs", job_id)
                await cache.delete(f"retry:{job_id}")
                moved += 1

        if moved:
            logger.info("Moved %d retry jobs back to active queues", moved)
        return moved

    def register_handler(
        self,
        queue_name: str,
        handler: Callable[[Job], Awaitable[dict]],
    ) -> None:
        self._handlers[queue_name] = handler
        logger.info("Registered handler for queue: %s", queue_name)

    async def start_worker(
        self,
        queue_name: str,
        concurrency: int = 1,
    ) -> None:
        if queue_name not in self._handlers:
            raise ValueError(f"No handler registered for queue: {queue_name}")

        handler = self._handlers[queue_name]
        workers = []

        for i in range(concurrency):
            task = asyncio.create_task(
                self._worker_loop(queue_name, handler, worker_id=i),
                name=f"worker-{queue_name}-{i}",
            )
            workers.append(task)

        self._workers[queue_name] = workers
        self._running = True

        logger.info(
            "Started %d worker(s) for queue: %s",
            concurrency,
            queue_name,
        )

    async def _worker_loop(
        self,
        queue_name: str,
        handler: Callable[[Job], Awaitable[dict]],
        worker_id: int = 0,
    ) -> None:
        logger.info("Worker %s-%d started", queue_name, worker_id)

        while self._running:
            try:
                job = await self.dequeue(queue_name, timeout=2)
                if not job:
                    await asyncio.sleep(0.5)
                    continue

                try:
                    result = await handler(job)
                    await self.complete_job(job, result)
                except Exception as exc:
                    logger.error(
                        "Worker %s-%d: Job %s failed: %s",
                        queue_name,
                        worker_id,
                        job.id,
                        exc,
                        exc_info=True,
                    )
                    await self.fail_job(job, str(exc))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Worker %s-%d error: %s", queue_name, worker_id, exc)
                await asyncio.sleep(1)

        logger.info("Worker %s-%d stopped", queue_name, worker_id)

    async def stop_workers(self) -> None:
        self._running = False
        for queue_name, workers in self._workers.items():
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        logger.info("All workers stopped")

    async def get_queue_stats(self, queue_name: str) -> dict:
        stats = {}
        for priority in [Priority.HIGH, Priority.MEDIUM, Priority.LOW]:
            key = f"queue:{queue_name}:{priority.value}"
            length = await cache._client.llen(key) if cache._client else 0
            stats[priority.value] = length

        dlq_key = f"deadletter:{queue_name}"
        dlq_length = await cache._client.llen(dlq_key) if cache._client else 0

        completed_key = f"completed:{queue_name}"
        completed_length = await cache._client.llen(completed_key) if cache._client else 0

        scheduled_count = await cache._client.zcard("scheduled_jobs") if cache._client else 0
        retry_count = await cache._client.zcard("retry_jobs") if cache._client else 0

        return {
            "queue": queue_name,
            "pending": stats,
            "dead_letter": dlq_length,
            "completed": completed_length,
            "scheduled": scheduled_count,
            "retrying": retry_count,
            "workers": len(self._workers.get(queue_name, [])),
        }

    async def get_job_status(self, job_id: str) -> dict | None:
        data = await cache.get(f"job:{job_id}")
        if data:
            return json.loads(data)
        return None

    async def get_all_queue_names(self) -> list[str]:
        if not cache._client:
            return []

        keys = await cache._client.keys("queue:*:high")
        queue_names = set()
        for key in keys:
            parts = key.split(":")
            if len(parts) == 3:
                queue_names.add(parts[1])
        return sorted(queue_names)

    async def reconcile_dead_letter_queue(
        self,
        queue_name: str,
        max_retries: int = 3,
    ) -> int:
        dlq_key = f"deadletter:{queue_name}"
        reconciled = 0

        if not cache._client:
            return 0

        total = await cache._client.llen(dlq_key)
        for _ in range(total):
            job_data = await cache.rpop(dlq_key)
            if not job_data:
                break

            job = Job.from_dict(json.loads(job_data))

            if job.retry_count >= max_retries:
                logger.warning(
                    "Dropping job %s from DLQ after %d retries",
                    job.id,
                    job.retry_count,
                )
                continue

            job.retry_count += 1
            job.status = JobStatus.PENDING.value
            job.error = None

            priority_queue = f"queue:{job.queue}:{job.priority}"
            await cache.lpush(priority_queue, json.dumps(job.to_dict()))
            await cache.set(
                f"job:{job.id}",
                json.dumps(job.to_dict()),
                ttl=self.JOB_TTL,
            )
            reconciled += 1

        if reconciled:
            logger.info(
                "Reconciled %d jobs from DLQ for queue %s",
                reconciled,
                queue_name,
            )
        return reconciled

    @staticmethod
    def _compute_dedup_key(queue: str, payload: dict) -> str:
        raw = json.dumps({"queue": queue, "payload": payload}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


class DLQReconciler:
    """
    Reconciles dead letter queue entries with exponential backoff retry.
    """

    def __init__(self, task_queue: TaskQueue):
        self.task_queue = task_queue

    async def reconcile_all_queues(self, max_retries: int = 3) -> dict[str, int]:
        queue_names = await self.task_queue.get_all_queue_names()
        results = {}

        for queue_name in queue_names:
            count = await self.task_queue.reconcile_dead_letter_queue(
                queue_name,
                max_retries=max_retries,
            )
            results[queue_name] = count

        return results


task_queue = TaskQueue()
dlq_reconciler = DLQReconciler(task_queue)
