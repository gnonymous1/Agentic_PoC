"""
GNONE — Social API Integration Service.
Concurrent dispatchers for Meta Graph, X API v2, and Google Blogger.
"""

import os
import logging
from typing import Dict, Any, List

import httpx

from app.core.circuit_breaker import openrouter_breaker
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)


async def dispatch_to_meta(token: str, body: str) -> Dict[str, Any]:
    """Publish to Meta Graph API (Facebook/Instagram)."""
    logger.info("SocialAPI: Publishing to Meta Graph")
    await limiter.acquire("social_api")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post("https://graph.facebook.com/v19.0/me/feed", json={"message": body, "access_token": token})
            resp.raise_for_status()
            return {"platform": "meta", "status": "success", "response": resp.json()}
        except Exception as exc:
            logger.error("Meta Graph API failed: %s", exc)
            return {"platform": "meta", "status": "failed", "error": str(exc)}


async def dispatch_to_x(token: str, posts: List[str]) -> Dict[str, Any]:
    """Publish thread to X API v2."""
    logger.info("SocialAPI: Publishing thread to X API v2")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    results = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for i, post in enumerate(posts):
            await limiter.acquire("social_api")
            try:
                resp = await client.post("https://api.twitter.com/2/tweets", headers=headers, json={"text": post})
                resp.raise_for_status()
                results.append(resp.json())
            except Exception as exc:
                logger.error("X API tweet %d failed: %s", i + 1, exc)
                results.append({"error": str(exc)})

    return {"platform": "x", "status": "success", "responses": results}


async def dispatch_to_blogspot(token: str, title: str, html_body: str) -> Dict[str, Any]:
    """Publish long-form article to Google Blogger REST API."""
    logger.info("SocialAPI: Publishing to Google Blogger")
    blog_id = os.getenv("GOOGLE_BLOGGER_BLOG_ID", "default")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    await limiter.acquire("social_api")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts",
                headers=headers,
                json={"kind": "blogger#post", "title": title, "content": html_body},
            )
            resp.raise_for_status()
            return {"platform": "blogspot", "status": "success", "response": resp.json()}
        except Exception as exc:
            logger.error("Google Blogger API failed: %s", exc)
            return {"platform": "blogspot", "status": "failed", "error": str(exc)}


async def dispatch_all_concurrently(payload: dict, tokens: dict) -> Dict[str, Any]:
    """Dispatch content to all platforms concurrently with failure isolation."""
    import asyncio

    meta_task = dispatch_to_meta(tokens.get("meta", ""), payload.get("linkedin", {}).get("body", ""))
    x_task = dispatch_to_x(tokens.get("x", ""), payload.get("twitter", {}).get("posts", []))
    blogspot_task = dispatch_to_blogspot(tokens.get("blogspot", ""), payload.get("blogspot", {}).get("title", ""), payload.get("blogspot", {}).get("html_body", ""))

    results = await asyncio.gather(meta_task, x_task, blogspot_task, return_exceptions=True)

    summary = {}
    for idx, platform in enumerate(["meta", "x", "blogspot"]):
        res = results[idx]
        if isinstance(res, Exception):
            summary[platform] = {"status": "failed", "error": str(res)}
        else:
            summary[platform] = res

    return summary
