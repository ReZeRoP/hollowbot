"""
Async SQLAlchemy engine + session factory.

Works with both SQLite (sqlite+aiosqlite) and PostgreSQL (postgresql+asyncpg)
transparently — the driver is chosen by DATABASE_URL.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# `echo=False` in prod; flip to True to debug SQL.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    # SQLite needs this to be usable across asyncio tasks
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
)

SessionFactory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    """Yield a session (used by middleware / scripts)."""
    async with SessionFactory() as session:
        yield session
