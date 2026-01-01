from sqlalchemy.engine import make_url

from ade_api.db.database import DatabaseConfig, build_async_url, build_sync_url


def test_build_sync_url_removes_sql_credentials_for_managed_identity() -> None:
    cfg = DatabaseConfig(
        url=(
            "mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade"
            "?Trusted_Connection=yes"
        ),
        auth_mode="managed_identity",
    )

    url = make_url(build_sync_url(cfg))

    assert url.username is None
    assert url.password is None
    assert "Trusted_Connection" not in url.query


def test_build_async_url_converts_sqlite_and_mssql_drivers() -> None:
    sqlite_cfg = DatabaseConfig(url="sqlite:///./data/db/ade.sqlite")
    assert build_async_url(sqlite_cfg).startswith("sqlite+aiosqlite:///")

    mssql_cfg = DatabaseConfig(
        url="mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade",
    )
    assert build_async_url(mssql_cfg).startswith("mssql+aioodbc://")
