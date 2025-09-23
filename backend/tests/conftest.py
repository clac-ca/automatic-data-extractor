"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.settings import reset_settings_cache
from backend.app.db.engine import render_sync_url, reset_database_state
from backend.app.main import create_app


@pytest.fixture(scope="session")
def _database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Provide a file-backed SQLite database URL for the test session."""

    db_path = tmp_path_factory.mktemp("ade-db") / "backend.sqlite"
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(scope="session", autouse=True)
def _configure_database(_database_url: str) -> AsyncIterator[None]:
    """Apply Alembic migrations against the ephemeral test database."""

    os.environ["ADE_DATABASE_URL"] = _database_url
    reset_settings_cache()
    reset_database_state()

    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", render_sync_url(_database_url))
    command.upgrade(config, "head")

    yield

    command.downgrade(config, "base")
    reset_database_state()
    reset_settings_cache()
    os.environ.pop("ADE_DATABASE_URL", None)


@pytest.fixture(scope="session")
def app(_configure_database: None) -> FastAPI:
    """Return an application instance for integration-style tests."""

    return create_app()


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Provide an HTTPX async client bound to the FastAPI app."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
