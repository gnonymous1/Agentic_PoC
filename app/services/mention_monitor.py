"""Background mention/notification monitor for social platforms.

Polls provider APIs for mentions and enqueues responses for HITL or auto-reply.
"""
import logging

from app.services.platform_dispatcher import get_token_for_client_platform
from database.connection import get_session
from database.models import OAuthVault

logger = logging.getLogger(__name__)


async def poll_mentions_job() -> None:
    logger.info("Polling mentions across connected accounts (prototype)")
    # For prototype, simply log connected accounts and simulate finding mentions
    db_session = await anext(get_session())
    rows = await db_session.execute(__import__("sqlalchemy").select(OAuthVault))
    vaults = rows.scalars().all()
    for v in vaults:
        try:
            token = await get_token_for_client_platform(str(v.client_id), v.platform)
            # In production, call platform APIs to fetch mentions and enqueue replies
            logger.info("Checked mentions for client=%s platform=%s", v.client_id, v.platform)
        except Exception as exc:
            logger.debug("Skipping mention check for client=%s platform=%s: %s", v.client_id, v.platform, exc)
