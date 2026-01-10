from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from ade_api.db import DatabaseSettings, build_engine


def test_mssql_smoke_select_one() -> None:
    if os.getenv("RUN_MSSQL_TESTS") != "1":
        pytest.skip("RUN_MSSQL_TESTS not set")

    url = os.getenv("ADE_DATABASE_URL", "")
    if not url.lower().startswith("mssql"):
        pytest.skip("ADE_DATABASE_URL must be mssql+pyodbc for this test")

    settings = DatabaseSettings.from_env()
    engine = build_engine(settings)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
