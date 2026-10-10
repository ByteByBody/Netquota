"""Database engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _engine_kwargs() -> tuple[str, dict]:
    settings = get_settings()
    url = settings.database_url
    connect_args: dict = {}
    kwargs: dict = {}
    if settings.is_sqlite:
        # Enable foreign keys on SQLite connections.
        connect_args["check_same_thread"] = False
        if ":memory:" in url or url.endswith("netquota.db"):
            pass
        if url.endswith(":memory:"):
            kwargs["poolclass"] = StaticPool
    return url, {**kwargs, "connect_args": connect_args, "future": True}


_url, _kwargs = _engine_kwargs()
engine = create_async_engine(_url, echo=False, **_kwargs)

if get_settings().is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - driver glue
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session."""
    async with SessionLocal() as session:
        yield session