"""
Async SQLAlchemy 2.0 engine and session factory for SEPE.
Wraps the existing asyncpg pool with SQLAlchemy ORM capabilities.
"""

import os
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://gnone:gnone@localhost:5432/gnone",
)


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_engine(
    database_url: str | None = None,
    pool_size: int = 10,
    max_overflow: int = 5,
    echo: bool = False,
) -> AsyncEngine:
    global _engine, _async_session_maker
    url = database_url or _DATABASE_URL
    _engine = create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    _async_session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("SQLAlchemy engine initialized — pool_size=%d url=%s", pool_size, url)
    return _engine


async def close_engine() -> None:
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("SQLAlchemy engine disposed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _async_session_maker is None:
        await init_engine()
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    if _engine is None:
        await init_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")


async def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        await init_engine()
    return _engine
