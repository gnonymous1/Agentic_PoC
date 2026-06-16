"""
GNONE — Queue Management API Routes

FastAPI routes for queue monitoring, job submission, and worker status.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.job_scheduler import job_scheduler
from app.services.redis_queue import Priority, task_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/queues", tags=["queues"])


class SubmitJobRequest(BaseModel):
    queue: str = Field(..., min_length=1, max_length=64)
    payload: dict = Field(...)
    priority: str = Field(default="medium")
    scheduled_at: str | None = None
    max_retries: int = Field(default=3, ge=0, le=10)
    idempotency_key: str | None = Field(default=None, max_length=128)


class SubmitJobResponse(BaseModel):
    job_id: str
    status: str
    queue: str
    priority: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    queue: str
    priority: str
    payload: dict
    retry_count: int
    max_retries: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    error: str | None
    result: dict | None


class QueueStatsResponse(BaseModel):
    queue: str
    pending: dict
    dead_letter: int
    completed: int
    scheduled: int
    retrying: int
    workers: int


class ScheduleTaskResponse(BaseModel):
    name: str
    cron: str
    enabled: bool
    next_run: str | None
    last_run: str | None
    run_count: int


@router.post("/submit", response_model=SubmitJobResponse)
async def submit_job(request: SubmitJobRequest):
    valid_priorities = {"high": Priority.HIGH, "medium": Priority.MEDIUM, "low": Priority.LOW}
    priority = valid_priorities.get(request.priority.lower(), Priority.MEDIUM)

    scheduled_at = None
    if request.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at)
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=UTC)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid scheduled_at format. Use ISO 8601 (e.g., 2026-01-15T03:00:00Z)",
            )

    job_id = await task_queue.enqueue(
        queue=request.queue,
        payload=request.payload,
        priority=priority,
        dedup=True,
        scheduled_at=scheduled_at,
        max_retries=request.max_retries,
        idempotency_key=request.idempotency_key,
    )

    if job_id is None:
        raise HTTPException(
            status_code=409,
            detail="Duplicate or idempotent job rejected",
        )

    return SubmitJobResponse(
        job_id=job_id,
        status="scheduled" if scheduled_at else "pending",
        queue=request.queue,
        priority=priority.value,
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job_data = await task_queue.get_job_status(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatusResponse(
        job_id=job_data.get("id", job_id),
        status=job_data.get("status", "unknown"),
        queue=job_data.get("queue", ""),
        priority=job_data.get("priority", "medium"),
        payload=job_data.get("payload", {}),
        retry_count=job_data.get("retry_count", 0),
        max_retries=job_data.get("max_retries", 3),
        created_at=job_data.get("created_at", ""),
        started_at=job_data.get("started_at"),
        completed_at=job_data.get("completed_at"),
        error=job_data.get("error"),
        result=job_data.get("result"),
    )


@router.get("/stats/{queue_name}", response_model=QueueStatsResponse)
async def get_queue_stats(queue_name: str):
    stats = await task_queue.get_queue_stats(queue_name)
    return QueueStatsResponse(**stats)


@router.get("/stats")
async def get_all_queue_stats():
    queue_names = await task_queue.get_all_queue_names()
    all_stats = {}

    for queue_name in queue_names:
        stats = await task_queue.get_queue_stats(queue_name)
        all_stats[queue_name] = stats

    return {
        "queues": all_stats,
        "total_queues": len(all_stats),
    }


@router.post("/dlq/reconcile/{queue_name}")
async def reconcile_dlq(
    queue_name: str,
    max_retries: int = Query(default=3, ge=0, le=10),
):
    count = await task_queue.reconcile_dead_letter_queue(
        queue_name,
        max_retries=max_retries,
    )
    return {
        "queue": queue_name,
        "reconciled": count,
        "status": "success",
    }


@router.post("/dlq/reconcile-all")
async def reconcile_all_dlq(
    max_retries: int = Query(default=3, ge=0, le=10),
):
    from app.services.redis_queue import dlq_reconciler
    results = await dlq_reconciler.reconcile_all_queues(max_retries=max_retries)
    return {
        "results": results,
        "total_reconciled": sum(results.values()),
        "status": "success",
    }


@router.post("/scheduled/process")
async def process_scheduled():
    scheduled_moved = await task_queue.process_scheduled_jobs()
    retry_moved = await task_queue.process_retry_jobs()
    return {
        "scheduled_moved": scheduled_moved,
        "retry_moved": retry_moved,
        "status": "success",
    }


@router.get("/scheduler/tasks")
async def list_scheduled_tasks():
    tasks = job_scheduler.get_task_status()
    return {"tasks": tasks, "count": len(tasks)}


@router.post("/scheduler/tasks/{name}/enable")
async def enable_task(name: str):
    if job_scheduler.enable_task(name):
        return {"name": name, "enabled": True, "status": "success"}
    raise HTTPException(status_code=404, detail=f"Task not found: {name}")


@router.post("/scheduler/tasks/{name}/disable")
async def disable_task(name: str):
    if job_scheduler.disable_task(name):
        return {"name": name, "enabled": False, "status": "success"}
    raise HTTPException(status_code=404, detail=f"Task not found: {name}")


@router.get("/health")
async def queue_health():
    from app.infrastructure.cache import cache

    redis_healthy = await cache.health()

    queue_names = await task_queue.get_all_queue_names()
    total_pending = 0
    total_dlq = 0

    for qn in queue_names:
        stats = await task_queue.get_queue_stats(qn)
        total_pending += sum(stats["pending"].values())
        total_dlq += stats["dead_letter"]

    return {
        "redis": "healthy" if redis_healthy else "degraded",
        "total_queues": len(queue_names),
        "total_pending": total_pending,
        "total_dead_letter": total_dlq,
        "scheduler_tasks": len(job_scheduler.get_task_status()),
    }
