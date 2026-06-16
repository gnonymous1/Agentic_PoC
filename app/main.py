import logging

from fastapi import FastAPI

from app.config import settings
from app.routes.content_manufacturing import router as content_router
from app.routes.oauth import router as oauth_router
from app.routes.support_chat import router as support_chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SEPE — Sovereign Executive Proxy Engine",
    description=(
        "Enterprise-grade digital clone platform. Creates hyper-realistic, "
        "multi-modal digital twins of business executives to autonomously "
        "manage their digital presence, communications, and real-time meetings."
    ),
    version="1.0.0",
)

# ── Dashboard (root) ──────────────────────────────────────────────────────
try:
    from app.routes.dashboard import router as dashboard_router
    app.include_router(dashboard_router)
except ImportError as exc:
    logger.warning("Dashboard router not available: %s", exc)

# ── Simulation (browser-based interactive demo) ───────────────────────────
try:
    from app.routes.simulation import router as simulation_router
    app.include_router(simulation_router)
except ImportError as exc:
    logger.warning("Simulation router not available: %s", exc)

# ── Content Manufacturing ─────────────────────────────────────────────────
app.include_router(content_router)
app.include_router(support_chat_router)
try:
    app.include_router(oauth_router)
except Exception:
    logger.warning("OAuth router not available, skipping")

# ── Admin, Analytics, Streaming, Webhooks ─────────────────────────────────
try:
    from app.routes.admin import router as admin_router
    app.include_router(admin_router)
except ImportError:
    logger.warning("Admin router not available, skipping")

try:
    from app.routes.analytics import router as analytics_router
    app.include_router(analytics_router)
except ImportError:
    logger.warning("Analytics router not available, skipping")

try:
    from app.routes.streaming import router as streaming_router
    app.include_router(streaming_router)
except ImportError:
    logger.warning("Streaming router not available, skipping")

try:
    from app.routes.webhooks import router as webhooks_router
    app.include_router(webhooks_router)
except ImportError:
    logger.warning("Webhooks router not available, skipping")

# ── Live Operations (real endpoints for dashboard) ──────────────────────────
try:
    from app.routes.live import router as live_router
    app.include_router(live_router)
except ImportError as exc:
    logger.warning("Live router not available: %s", exc)

# ── RAG Pipeline ────────────────────────────────────────────────────────────
try:
    from app.routes.rag import router as rag_router
    app.include_router(rag_router)
except ImportError as exc:
    logger.warning("RAG router not available: %s", exc)

try:
    from app.routes.accounts import router as accounts_router
    app.include_router(accounts_router)
except Exception:
    logger.warning("Accounts router not available, skipping")

try:
    from app.routes.scheduled_posts import router as scheduled_router
    app.include_router(scheduled_router)
except Exception:
    logger.warning("Scheduled posts router not available, skipping")

# ── Queue Management ────────────────────────────────────────────────────────
try:
    from app.routes.queues import router as queues_router
    app.include_router(queues_router)
except ImportError as exc:
    logger.warning("Queues router not available: %s", exc)


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("  SEPE — Sovereign Executive Proxy Engine")
    logger.info("=" * 60)
    logger.info("  Generator model:     %s", settings.generator_model)
    logger.info("  Fallback model:      %s", settings.generator_fallback_model)
    logger.info("  Critic model:        %s", settings.critic_model)
    logger.info("  Grounding model:     %s", "gemini-3.1-flash-lite")
    logger.info("  Voice provider:      %s", "ElevenLabs / Cartesia")
    logger.info("  Max critic retries:  %d", 2)
    logger.info("  Agent timeout:       %ds", 90)
    logger.info("=" * 60)
    logger.info("  Dashboard:           http://localhost:8080")
    logger.info("  API docs:            http://localhost:8080/docs")
    logger.info("  Simulation:          http://localhost:8080 (Simulation tab)")
    logger.info("=" * 60)
    # Register default scheduled tasks and start the scheduler
    try:
        from app.services.job_scheduler import job_scheduler, register_default_schedules
        from app.services.social_dispatcher import register_dispatcher_handlers

        register_default_schedules()
        register_dispatcher_handlers()
        await job_scheduler.start()
    except Exception as exc:
        logger.warning("Scheduler/service startup incomplete: %s", exc)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SEPE shutting down...")
    logger.info("Draining active connections...")
    logger.info("Shutdown complete.")
