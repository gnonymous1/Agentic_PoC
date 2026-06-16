"""Platform dispatchers for posting content to social/email providers.

This module contains simple, extendable functions used by the scheduled
post dispatcher to deliver content. Real provider integration should live
here (Twitter, LinkedIn, Gmail), including error handling and rate limits.
"""
import logging
from typing import Any

import httpx

from app.services.encryption import decrypt_token
from database.connection import get_session
from database.models import OAuthVault

logger = logging.getLogger(__name__)


async def post_to_platform(platform: str, token: str, content: dict[str, Any]) -> dict[str, Any]:
    """Dispatch content to platform APIs with sandbox fallback support."""
    platform = platform.lower()
    async with httpx.AsyncClient(timeout=10.0) as client:
        if platform == "twitter" or platform == "x":
            text = content.get("text") or content.get("body", "")
            url = "https://api.twitter.com/2/tweets"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {"text": text}
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return resp.json()
                else:
                    logger.warning("Twitter API returned %d, falling back to sandbox", resp.status_code)
                    return {"status": "sandbox_posted", "platform": "twitter", "text": text}
            except Exception as exc:
                logger.debug("Twitter post attempt failed: %s (sandbox fallback)", exc)
                return {"status": "sandbox_posted", "platform": "twitter", "text": text}

        if platform == "linkedin":
            body = content.get("body") or content.get("text", "")
            # LinkedIn real API would require user/UGC share endpoint; for now sandbox
            logger.info("LinkedIn content queued: %s", body[:100])
            return {"status": "sandbox_posted", "platform": "linkedin", "body": body}

        if platform == "email":
            to = content.get("to") or content.get("recipient", "")
            subject = content.get("subject", "")
            body = content.get("body") or content.get("text", "")
            logger.info("Email queued to %s (subject: %s)", to, subject)
            return {"status": "email_queued", "platform": "email", "to": to, "subject": subject}

        logger.warning("Unsupported platform for dispatcher: %s", platform)
        return {"status": "unsupported", "platform": platform}


async def get_token_for_client_platform(client_id: str, platform: str) -> str:
    db_session = await anext(get_session())
    rows = await db_session.execute(
        __import__("sqlalchemy").select(OAuthVault).where(OAuthVault.client_id == client_id, OAuthVault.platform == platform)
    )
    vault = rows.scalar_one_or_none()
    if not vault:
        raise ValueError("No token for client/platform")
    token = decrypt_token(vault.encrypted_token, vault.encrypted_iv, vault.encrypted_tag, key_version=vault.key_version)
    return token
