from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI

from ade_api.db.session import get_sessionmaker
from ade_api.settings import get_settings


@pytest_asyncio.fixture()
async def session(app: FastAPI):
    """Return a database session bound to the test application's database."""

    settings = getattr(app.state, "settings", None) or get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        yield session
