"""Runtime helpers for the ADE command-line interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ade.settings import Settings, get_settings, reload_settings
from ade.db.bootstrap import ensure_database_ready
from ade.db.session import get_sessionmaker
from ade.lifecycles import ensure_runtime_dirs

__all__ = [
    "load_settings",
    "open_session",
    "normalise_email",
    "read_secret",
]


def load_settings() -> Settings:
    """Return ADE settings using the same loader as the API."""

    settings = reload_settings()
    # Allow subsequent calls to `get_settings()` to reflect environment changes made
    # outside the CLI command invocation.
    get_settings.cache_clear()
    return settings


@asynccontextmanager
async def open_session(
    settings: Settings | None = None,
) -> AsyncIterator[AsyncSession]:
    """Yield an ``AsyncSession`` with commit/rollback semantics."""

    resolved = settings or get_settings()
    ensure_runtime_dirs(resolved)
    await ensure_database_ready(resolved)
    session_factory = get_sessionmaker(settings=resolved)
    session = session_factory()
    try:
        yield session
        if session.in_transaction():
            await session.commit()
    except Exception:  # pragma: no cover - defensive rollback
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        await session.close()


def normalise_email(value: str) -> str:
    """Return a canonical email representation for comparisons."""

    candidate = value.strip()
    if not candidate:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return candidate.lower()


def read_secret(path: str | Path) -> str:
    """Return the first line of ``path`` stripped of trailing whitespace."""

    file_path = Path(path).expanduser()
    try:
        first_line = file_path.read_text(encoding="utf-8").splitlines()[0]
    except IndexError as exc:
        msg = f"Secret file '{file_path}' is empty"
        raise ValueError(msg) from exc
    except FileNotFoundError as exc:  # pragma: no cover - guardrails
        msg = f"Secret file '{file_path}' not found"
        raise ValueError(msg) from exc
    return first_line.strip()
