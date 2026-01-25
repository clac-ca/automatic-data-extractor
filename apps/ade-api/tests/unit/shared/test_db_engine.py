import pytest
from ade_api.db import build_engine
from ade_api.settings import Settings


def test_build_engine_strips_sql_credentials_for_managed_identity() -> None:
    pytest.importorskip("pyodbc")
    settings = Settings(
        _env_file=None,
        database_url_override=(
            "mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade"
            "?Trusted_Connection=yes"
        ),
        database_auth_mode="managed_identity",
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
    pytest.importorskip("pyodbc")
    settings = Settings(
        _env_file=None,
        database_url_override="mssql://user:secret@contoso.database.windows.net:1433/ade",
    )
    engine = build_engine(settings)
    try:
        assert engine.url.drivername.startswith("mssql+pyodbc")
    finally:
        engine.dispose()


def test_build_engine_rejects_non_mssql_urls() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url_override="postgresql://user:pass@localhost:5432/ade")
