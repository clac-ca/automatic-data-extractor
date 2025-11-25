from __future__ import annotations

import pytest
from fastapi import FastAPI

from ade_api.settings import get_settings
from ade_api.shared.db.session import get_sessionmaker


@pytest.fixture()
async def session(app: FastAPI):
    """Return a database session bound to the test application's database."""

    settings = getattr(app.state, "settings", None) or get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        yield session
