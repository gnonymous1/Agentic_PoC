"""
Integration tests for webhook endpoints.
Uses httpx AsyncClient with ASGI transport against the FastAPI app.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_zapier_webhook_enqueues(monkeypatch):
    enqueued = []

    async def mock_enqueue(queue, payload):
        enqueued.append((queue, payload))
        return "mock-request-id"

    import app.routes.webhooks as wh
    monkeypatch.setattr(wh.task_queue, "enqueue", mock_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "topic": "AI trends 2026",
            "brand_voice": "Professional",
            "target_platforms": ["twitter", "linkedin"],
        }
        response = await client.post("/api/v1/webhooks/zapier/content", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["request_id"] == "mock-request-id"
    assert len(enqueued) == 1
    assert enqueued[0][0] == "zapier:content"
    assert enqueued[0][1] == payload


@pytest.mark.asyncio
async def test_wordpress_webhook_queues(monkeypatch):
    enqueued = []

    async def mock_enqueue(queue, payload):
        enqueued.append((queue, payload))
        return "mock-id"

    import app.routes.webhooks as wh
    monkeypatch.setattr(wh.task_queue, "enqueue", mock_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "content_id": "wp-123",
            "blogspot_html": "<p>Hello world</p>",
            "title": "Test Post",
            "seo_slug": "test-post",
        }
        response = await client.post("/api/v1/webhooks/wordpress/publish", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued_for_publish"
    assert len(enqueued) == 1
    assert enqueued[0][0] == "wordpress:publish"


@pytest.mark.asyncio
async def test_shopify_webhook_queues(monkeypatch):
    enqueued = []

    async def mock_enqueue(queue, payload):
        enqueued.append((queue, payload))
        return "mock-id"

    import app.routes.webhooks as wh
    monkeypatch.setattr(wh.task_queue, "enqueue", mock_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "content_id": "shop-456",
            "blogspot_html": "<p>Shopify article</p>",
            "title": "Shopify Post",
        }
        response = await client.post("/api/v1/webhooks/shopify/publish", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued_for_publish"
    assert len(enqueued) == 1
    assert enqueued[0][0] == "shopify:publish"


@pytest.mark.asyncio
async def test_webhook_hmac_validation(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "test-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"topic": "test"}
        response = await client.post("/api/v1/webhooks/zapier/content", json=payload)

    assert response.status_code in (401, 403)
