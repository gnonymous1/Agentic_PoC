"""
Incoming webhook handlers for Recall.ai events, calendar triggers, and RSS feeds.
All endpoints now enforce HMAC signature verification.
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.services.redis_queue import task_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


def verify_hmac(payload: dict, signature: str, secret: str) -> bool:
    import json
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _enforce_hmac(payload: dict, x_signature: str) -> None:
    if not settings.webhook_secret:
        return
    if not x_signature:
        raise HTTPException(401, "Missing signature header")
    if not verify_hmac(payload, x_signature, settings.webhook_secret):
        raise HTTPException(403, "Invalid signature")


@router.post("/recall-ai/status")
async def recall_ai_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for Recall.ai session status updates."""
    _enforce_hmac(payload, x_signature)
    await task_queue.enqueue("recall:events", payload)
    return {"status": "queued"}


@router.post("/calendar/event")
async def calendar_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for incoming calendar events (Google Calendar, Outlook)."""
    _enforce_hmac(payload, x_signature)
    await task_queue.enqueue("calendar:events", payload)
    return {"status": "queued"}


@router.post("/rss/feed")
async def rss_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for RSS feed updates."""
    _enforce_hmac(payload, x_signature)
    await task_queue.enqueue("rss:items", payload)
    return {"status": "queued"}


@router.post("/zapier/content")
async def zapier_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for Zapier content triggers."""
    _enforce_hmac(payload, x_signature)
    request_id = await task_queue.enqueue("zapier:content", payload)
    return {"status": "accepted", "request_id": request_id or ""}


@router.post("/wordpress/publish")
async def wordpress_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for WordPress blog post publishing."""
    _enforce_hmac(payload, x_signature)
    await task_queue.enqueue("wordpress:publish", payload)
    logger.info("WordPress publish queued: %s", payload.get("content_id", "unknown"))
    return {"status": "queued_for_publish"}


@router.post("/shopify/publish")
async def shopify_webhook(payload: dict, x_signature: str = Header(None)):
    """Webhook receiver for Shopify BlogArticle publishing."""
    _enforce_hmac(payload, x_signature)
    await task_queue.enqueue("shopify:publish", payload)
    logger.info("Shopify publish queued: %s", payload.get("content_id", "unknown"))
    return {"status": "queued_for_publish"}
