from __future__ import annotations

from sqlalchemy import text

from ade_api.db import build_engine


def test_mssql_smoke_select_one(base_settings) -> None:
    engine = build_engine(base_settings)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
