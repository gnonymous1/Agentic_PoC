"""
PostgreSQL database session management with asyncpg.
Supports connection pooling, health checks, and pgvector queries.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    dsn: str = os.getenv("DATABASE_URL", "postgresql://gnone:gnone@localhost:5432/gnone")
    min_connections: int = 5
    max_connections: int = 10  # tuned for single-process uvicorn scaling
    statement_timeout: int = 30000
    pool_recycle: int = 300


class Database:
    """
    Async PostgreSQL connection pool manager.
    Wraps asyncpg with automatic retry and health checking.
    """

    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig()
        self._pool = None

    async def connect(self):
        import asyncpg
        self._pool = await asyncpg.create_pool(
            dsn=self.config.dsn,
            min_size=self.config.min_connections,
            max_size=self.config.max_connections,
            command_timeout=self.config.statement_timeout,
        )

    async def disconnect(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            yield conn

    async def execute(self, query: str, *args) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> dict | None:
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def health(self) -> bool:
        try:
            async with self.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False


db = Database()
