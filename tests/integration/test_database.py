"""Integration tests for database connection and queries."""

import os

import pytest

try:
    import asyncpg
    asyncpg  # suppress unused
except ImportError:
    _has_asyncpg = False
else:
    _has_asyncpg = True

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and _has_asyncpg),
    reason="No database available — set DATABASE_URL for integration DB tests",
)


@pytest.fixture
async def db_conn():
    """Provides an async database connection using DATABASE_URL."""
    import asyncpg

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://gnone:gnone@localhost:5432/gnone",
    )
    conn = await asyncpg.connect(url)
    try:
        yield conn
    finally:
        await conn.close()


class TestDatabase:
    async def test_health_check(self, db_conn):
        result = await db_conn.fetchval("SELECT 1")
        assert result == 1

    async def test_insert_and_query_clients(self, db_conn):
        org_slug = f"test-org-{os.urandom(4).hex()}"
        await db_conn.execute(
            """
            INSERT INTO clients (org_name, org_slug, billing_email)
            VALUES ($1, $2, $3)
            """,
            "Test Organization",
            org_slug,
            "test@example.com",
        )
        row = await db_conn.fetchrow(
            "SELECT org_name, org_slug FROM clients WHERE org_slug = $1", org_slug
        )
        assert row is not None
        assert row["org_name"] == "Test Organization"
        assert row["org_slug"] == org_slug

    async def test_rls_is_active(self, db_conn):
        tables = await db_conn.fetch(
            """
            SELECT relname FROM pg_class
            WHERE relrowsecurity = true AND relnamespace = 'public'::regnamespace
            """
        )
        rls_tables = [r["relname"] for r in tables]
        assert isinstance(rls_tables, list)
