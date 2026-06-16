"""
GNONE — Cron-like Job Scheduler

Handles overnight tasks, periodic health checks, token rotation,
and scheduled job orchestration.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.infrastructure.cache import cache
from app.services.mention_monitor import poll_mentions_job
from app.services.redis_queue import Priority, task_queue
from database.connection import get_session
from database.models import ScheduledPost

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    name: str
    cron_expression: str
    handler: Callable[[], Awaitable[None]]
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    enabled: bool = True
    timeout_seconds: int = 300
    queue_name: str | None = None
    queue_payload: dict | None = None


class CronParser:
    """
    Minimal cron expression parser supporting:
    minute hour day_of_month month day_of_week
    Special values: * */N N N,M N-M
    """

    @staticmethod
    def parse_field(expr: str, min_val: int, max_val: int) -> set[int]:
        values = set()
        for part in expr.split(","):
            if "/" in part:
                base, step = part.split("/", 1)
                step = int(step)
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                values.update(range(start, max_val + 1, step))
            elif "-" in part:
                start, end = part.split("-", 1)
                values.update(range(int(start), int(end) + 1))
            elif part == "*":
                values.update(range(min_val, max_val + 1))
            else:
                values.add(int(part))
        return values

    @classmethod
    def matches(cls, cron_expr: str, dt: datetime) -> bool:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")

        minute, hour, day, month, dow = parts

        minute_vals = cls.parse_field(minute, 0, 59)
        hour_vals = cls.parse_field(hour, 0, 23)
        day_vals = cls.parse_field(day, 1, 31)
        month_vals = cls.parse_field(month, 1, 12)
        dow_vals = cls.parse_field(dow, 0, 6)

        return (
            dt.minute in minute_vals
            and dt.hour in hour_vals
            and dt.day in day_vals
            and dt.month in month_vals
            and dt.weekday() in dow_vals
        )

    @classmethod
    def next_run(cls, cron_expr: str, from_dt: datetime | None = None) -> datetime:
        if from_dt is None:
            from_dt = datetime.now(UTC)

        current = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(525600):
            if cls.matches(cron_expr, current):
                return current
            current += timedelta(minutes=1)

        raise ValueError(f"Could not find next run for: {cron_expr}")


class JobScheduler:
    """
    Cron-like scheduler for periodic tasks including:
    - Overnight batch processing
    - Periodic health checks
    - Token rotation
    - Queue maintenance
    """

    CHECK_INTERVAL = 30

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: asyncio.Task | None = None

    def add_task(
        self,
        name: str,
        cron_expression: str,
        handler: Callable[[], Awaitable[None]],
        enabled: bool = True,
        timeout_seconds: int = 300,
    ) -> None:
        task = ScheduledTask(
            name=name,
            cron_expression=cron_expression,
            handler=handler,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
        )
        task.next_run = CronParser.next_run(cron_expression)
        self._tasks[name] = task
        logger.info(
            "Scheduled task '%s' with cron '%s', next run: %s",
            name,
            cron_expression,
            task.next_run,
        )

    def add_queue_task(
        self,
        name: str,
        cron_expression: str,
        queue_name: str,
        payload: dict,
        priority: Priority = Priority.MEDIUM,
        enabled: bool = True,
    ) -> None:
        async def queue_handler():
            await task_queue.enqueue(
                queue=queue_name,
                payload=payload,
                priority=priority,
                dedup=True,
            )

        self.add_task(
            name=name,
            cron_expression=cron_expression,
            handler=queue_handler,
            enabled=enabled,
        )

    def remove_task(self, name: str) -> bool:
        if name in self._tasks:
            del self._tasks[name]
            logger.info("Removed scheduled task: %s", name)
            return True
        return False

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(),
            name="job-scheduler",
        )
        logger.info("Job scheduler started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Job scheduler stopped")

    async def _scheduler_loop(self) -> None:
        while self._running:
            now = datetime.now(UTC)

            for name, task in self._tasks.items():
                if not task.enabled:
                    continue

                if task.next_run and now >= task.next_run:
                    await self._execute_task(name, task)

            await asyncio.sleep(self.CHECK_INTERVAL)

    async def _execute_task(self, name: str, task: ScheduledTask) -> None:
        logger.info("Executing scheduled task: %s", name)

        try:
            await asyncio.wait_for(
                task.handler(),
                timeout=task.timeout_seconds,
            )

            task.last_run = datetime.now(UTC)
            task.run_count += 1
            task.next_run = CronParser.next_run(task.cron_expression, task.last_run)

            logger.info(
                "Task '%s' completed successfully, next run: %s",
                name,
                task.next_run,
            )
        except TimeoutError:
            logger.error("Task '%s' timed out after %ds", name, task.timeout_seconds)
            task.next_run = CronParser.next_run(task.cron_expression)
        except Exception as exc:
            logger.error("Task '%s' failed: %s", name, exc, exc_info=True)
            task.next_run = CronParser.next_run(task.cron_expression)

    def get_task_status(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "cron": t.cron_expression,
                "enabled": t.enabled,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "run_count": t.run_count,
                "timeout_seconds": t.timeout_seconds,
            }
            for t in self._tasks.values()
        ]

    def enable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = True
            self._tasks[name].next_run = CronParser.next_run(
                self._tasks[name].cron_expression
            )
            return True
        return False

    def disable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = False
            return True
        return False


async def health_check_handler() -> None:
    logger.info("Running periodic health check")
    db_healthy = await _check_db_health()
    redis_healthy = await _check_redis_health()

    status = {
        "timestamp": datetime.now(UTC).isoformat(),
        "database": "healthy" if db_healthy else "degraded",
        "redis": "healthy" if redis_healthy else "degraded",
    }

    await cache.set(
        "health:last_check",
        json.dumps(status),
        ttl=300,
    )

    if not db_healthy or not redis_healthy:
        logger.warning("Health check reported degradation: %s", status)


async def token_rotation_handler() -> None:
    logger.info("Running token rotation check")
    await cache.set(
        "tokens:last_rotation",
        datetime.now(UTC).isoformat(),
        ttl=86400,
    )


async def overnight_cleanup_handler() -> None:
    logger.info("Running overnight cleanup")
    await task_queue.reconcile_dead_letter_queue("content_generation", max_retries=2)
    await task_queue.reconcile_dead_letter_queue("webhook_delivery", max_retries=2)


async def scheduled_jobs_maintenance_handler() -> None:
    logger.info("Running scheduled jobs maintenance")
    moved = await task_queue.process_scheduled_jobs()
    retried = await task_queue.process_retry_jobs()
    logger.info(
        "Maintenance: moved %d scheduled, %d retry jobs",
        moved,
        retried,
    )


async def _check_db_health() -> bool:
    try:
        from app.infrastructure.db import db
        return await db.health()
    except Exception:
        return False


async def _check_redis_health() -> bool:
    try:
        return await cache.health()
    except Exception:
        return False


job_scheduler = JobScheduler()


def register_default_schedules() -> None:
    job_scheduler.add_task(
        name="health_check",
        cron_expression="*/5 * * * *",
        handler=health_check_handler,
        timeout_seconds=30,
    )

    job_scheduler.add_task(
        name="token_rotation",
        cron_expression="0 3 * * 0",
        handler=token_rotation_handler,
        timeout_seconds=120,
    )

    job_scheduler.add_task(
        name="overnight_cleanup",
        cron_expression="0 2 * * *",
        handler=overnight_cleanup_handler,
        timeout_seconds=300,
    )

    job_scheduler.add_task(
        name="scheduled_jobs_maintenance",
        cron_expression="*/1 * * * *",
        handler=scheduled_jobs_maintenance_handler,
        timeout_seconds=60,
    )

    job_scheduler.add_task(
        name="poll_mentions",
        cron_expression="*/2 * * * *",
        handler=poll_mentions_job,
        timeout_seconds=30,
    )


async def process_scheduled_posts_handler() -> None:
    """Find scheduled posts due now and enqueue them to the task queue."""
    logger.info("Checking for due scheduled posts")
    now = datetime.now(UTC)
    try:
        db_session = await anext(get_session())
        stmt = select(ScheduledPost).where(
            ScheduledPost.status == "scheduled",
            ScheduledPost.scheduled_at <= now,
        )
        result = await db_session.execute(stmt)
        posts = result.scalars().all()

        for post in posts:
            # mark queued to avoid double-enqueue
            post.status = "queued"
            post.updated_at = datetime.now(UTC)
            await db_session.flush()

            payload = {
                "scheduled_post_id": str(post.id),
                "client_id": str(post.client_id),
                "platform": post.platform,
            }

            await task_queue.enqueue(
                queue="scheduled_post_dispatch",
                payload=payload,
                priority=Priority.MEDIUM,
                dedup=True,
            )

        if posts:
            logger.info("Enqueued %d scheduled posts", len(posts))
    except Exception as exc:
        logger.error("Error while processing scheduled posts: %s", exc, exc_info=True)


    # register periodic runner (runs every minute)
    job_scheduler.add_task(
        name="process_scheduled_posts",
        cron_expression="*/1 * * * *",
        handler=process_scheduled_posts_handler,
        timeout_seconds=30,
    )

    logger.info("Default schedules registered")
