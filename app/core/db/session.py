"""Session factories and FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.settings import Settings, get_app_settings, get_settings
from .engine import engine_cache_key, get_engine

_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None
_SESSION_KEY: tuple[Any, ...] | None = None


def reset_session_state() -> None:
    """Clear the cached session factory."""

    global _SESSION_FACTORY, _SESSION_KEY
    _SESSION_FACTORY = None
    _SESSION_KEY = None


def get_sessionmaker(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Return a cached ``async_sessionmaker`` bound to the ADE engine."""

    global _SESSION_FACTORY, _SESSION_KEY
    settings = settings or get_settings()
    cache_key = engine_cache_key(settings)
    if _SESSION_FACTORY is None or _SESSION_KEY != cache_key:
        engine = get_engine(settings)
        _SESSION_FACTORY = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )
        _SESSION_KEY = cache_key
    return _SESSION_FACTORY


def _get_sessionmaker_from_request(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    settings = get_app_settings(request.app)
    return get_sessionmaker(settings=settings)


SessionFactoryDependency = Annotated[
    async_sessionmaker[AsyncSession], Depends(_get_sessionmaker_from_request)
]


async def get_session(
    request: Request,
    session_factory: SessionFactoryDependency,
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an ``AsyncSession`` for the request."""

    session = session_factory()
    request.state.db_session = session
    try:
        yield session
        if session.in_transaction():
            await session.commit()
    except Exception:
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        if getattr(request.state, "db_session", None) is session:
            request.state.db_session = None
        await session.close()


__all__ = ["get_session", "get_sessionmaker", "reset_session_state"]
