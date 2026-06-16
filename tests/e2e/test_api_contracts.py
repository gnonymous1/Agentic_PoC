import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_manufacture_endpoint_returns_422_on_missing_topic():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/manufacture", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manufacture_endpoint_returns_422_on_short_topic():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/manufacture", json={"topic": "hi"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_admin_metrics_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/metrics")
    assert resp.status_code == 200
    assert "gnone_" in resp.text


@pytest.mark.asyncio
async def test_admin_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_analytics_dashboard_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_analytics_cost_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/analytics/cost?days=30")
    assert resp.status_code == 200
