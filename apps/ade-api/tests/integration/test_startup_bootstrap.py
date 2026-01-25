"""API bootstrap lifecycle tests."""

from __future__ import annotations

import pytest

from ade_api.main import create_app

pytestmark = pytest.mark.asyncio


async def test_app_startup_bootstraps_database(empty_database_settings) -> None:
    app = create_app(settings=empty_database_settings)

    with pytest.raises(RuntimeError, match="Database schema is not initialized"):
        async with app.router.lifespan_context(app):
            pass
