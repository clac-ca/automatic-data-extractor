from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from ade_api.db import DatabaseSettings, build_engine


def test_build_engine_strips_sql_credentials_for_managed_identity() -> None:
    settings = DatabaseSettings(
        url=(
            "mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade"
            "?Trusted_Connection=yes"
        ),
        auth_mode="managed_identity",
    )

    engine = build_engine(settings)
    try:
        url = engine.url
        assert url.username is None
        assert url.password is None
        assert "Trusted_Connection" not in (url.query or {})
    finally:
        engine.dispose()


def test_build_engine_normalizes_mssql_driver() -> None:
    settings = DatabaseSettings(url="mssql://user:secret@contoso.database.windows.net:1433/ade")
    engine = build_engine(settings)
    try:
        assert engine.url.drivername.startswith("mssql+pyodbc")
    finally:
        engine.dispose()


def test_build_engine_sqlite_in_memory_smoke() -> None:
    settings = DatabaseSettings(url="sqlite:///:memory:")
    engine = build_engine(settings)
    try:
        assert isinstance(engine.pool, StaticPool)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
