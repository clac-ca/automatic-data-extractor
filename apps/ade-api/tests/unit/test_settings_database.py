import pytest
from sqlalchemy.engine import make_url

from ade_api.settings import Settings


def test_non_mssql_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url_override="postgresql://user:pass@localhost:5432/ade")


def test_mssql_driver_defaults_to_odbc_18() -> None:
    settings = Settings(
        _env_file=None,
        sql_host="example.database.windows.net",
        sql_user="user",
        sql_password="pass",
        sql_database="ade",
    )

    assert "driver=ODBC+Driver+18+for+SQL+Server" in settings.database_url


def test_managed_identity_strips_credentials_from_dsn() -> None:
    settings = Settings(
        _env_file=None,
        sql_host="contoso.database.windows.net",
        sql_user="user",
        sql_password="secret",
        sql_database="ade",
        database_auth_mode="managed_identity",
    )

    url = make_url(settings.database_url)
    assert url.username is None
    assert url.password is None
    assert url.host == "contoso.database.windows.net"
    assert url.port == 1433
    assert url.database == "ade"
