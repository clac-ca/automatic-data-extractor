"""API bootstrap lifecycle tests."""

from __future__ import annotations

from ade_api.main import create_app
import pytest

pytestmark = pytest.mark.asyncio


async def test_app_startup_bootstraps_database(empty_database_settings) -> None:
    app = create_app(settings=empty_database_settings)

    async with app.router.lifespan_context(app):
        pass
