from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from ade_api.db import build_engine
from ade_api.settings import Settings


def test_mssql_smoke_select_one() -> None:
    if os.getenv("RUN_MSSQL_TESTS") != "1":
        pytest.skip("RUN_MSSQL_TESTS not set")

    if not os.getenv("ADE_SQL_HOST") or not os.getenv("ADE_SQL_PASSWORD"):
        pytest.skip("ADE_SQL_HOST and ADE_SQL_PASSWORD must be set for this test")

    settings = Settings()
    engine = build_engine(settings)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
