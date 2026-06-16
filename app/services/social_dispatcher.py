import logging
from datetime import UTC, datetime

from app.services.platform_dispatcher import get_token_for_client_platform, post_to_platform
from app.services.redis_queue import Job, task_queue
from database.connection import get_session
from database.models import ScheduledPost

logger = logging.getLogger(__name__)


async def _handle_scheduled_post(job: Job) -> dict:
    payload = job.payload or {}
    scheduled_post_id = payload.get("scheduled_post_id")
    if not scheduled_post_id:
        raise ValueError("scheduled_post_id missing in job payload")

    db_session = await anext(get_session())
    post = await db_session.get(ScheduledPost, scheduled_post_id)
    if not post:
        raise ValueError(f"ScheduledPost not found: {scheduled_post_id}")

    try:
        token = await get_token_for_client_platform(str(post.client_id), post.platform)
        result = await post_to_platform(post.platform, token, post.content)
        post.status = "posted"
        post.metadata["dispatch_response"] = result
        post.updated_at = datetime.now(UTC)
        await db_session.flush()

        logger.info("Dispatched scheduled post %s (platform=%s)", scheduled_post_id, post.platform)
        return {"scheduled_post_id": scheduled_post_id, "status": "posted", "response": result}
    except Exception as exc:
        post.status = "failed"
        post.updated_at = datetime.now(UTC)
        await db_session.flush()
        logger.error("Failed to dispatch scheduled post %s: %s", scheduled_post_id, exc)
        raise


def register_dispatcher_handlers():
    task_queue.register_handler("scheduled_post_dispatch", _handle_scheduled_post)
