import pytest
import pytest

from ade_api.settings import Settings


def test_managed_identity_requires_mssql_url() -> None:
    with pytest.raises(ValueError):
        Settings(database_auth_mode="managed_identity")


def test_mssql_driver_defaults_to_odbc_18() -> None:
    settings = Settings(
        database_dsn="mssql+pyodbc://user:pass@example.database.windows.net:1433/ade",
    )

    assert "driver=ODBC+Driver+18+for+SQL+Server" in settings.database_dsn


def test_managed_identity_strips_credentials_from_dsn() -> None:
    settings = Settings(
        database_dsn="mssql+pyodbc://user:secret@contoso.database.windows.net:1433/ade",
        database_auth_mode="managed_identity",
    )

    assert "user:secret" not in settings.database_dsn
    assert settings.database_dsn.startswith(
        "mssql+pyodbc://contoso.database.windows.net:1433/ade"
    )
