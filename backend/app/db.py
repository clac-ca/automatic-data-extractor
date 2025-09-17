"""Database utilities."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

Base = declarative_base()


def _is_sqlite_memory_url(url: URL) -> bool:
    """Return ``True`` when the URL points at an in-memory SQLite database."""

    database = (url.database or "").strip()
    if database in {"", ":memory:"}:
        return True
    if database.startswith("file:"):
        if database.endswith(":memory:"):
            return True
        mode = url.query.get("mode")
        if isinstance(mode, str) and mode.lower() == "memory":
            return True
    return False


def _create_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {"future": True}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if _is_sqlite_memory_url(url):
            engine_kwargs["poolclass"] = StaticPool

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    return create_engine(database_url, **engine_kwargs)


settings = get_settings()
engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for the request lifecycle."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]
