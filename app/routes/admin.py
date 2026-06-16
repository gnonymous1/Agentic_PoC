"""
Admin dashboard routes for platform management.
"""

from fastapi import APIRouter

from app.core.metrics import metrics_app

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    return metrics_app()


@router.get("/health")
async def health():
    """Aggregate health check for all dependencies."""
    from app.infrastructure.health import health_registry
    results = await health_registry.check_all()
    all_healthy = all(r.healthy for r in results)
    status_code = 200 if all_healthy else 503
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": [
            {"service": r.service, "healthy": r.healthy, "latency_ms": r.latency_ms}
            for r in results
        ],
    }


@router.post("/cache/flush")
async def flush_cache():
    """Flush Redis cache (admin only)."""
    from app.infrastructure.cache import cache
    if cache._client:
        await cache._client.flushall()
    return {"status": "cache flushed"}
