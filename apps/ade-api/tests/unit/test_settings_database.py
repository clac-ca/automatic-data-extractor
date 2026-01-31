import pytest
from sqlalchemy.engine import make_url

from ade_api.settings import Settings


def test_non_postgres_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            database_url="mysql://user:pass@localhost:3306/ade",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )


def test_postgres_driver_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/ade",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )
    url = make_url(str(settings.database_url))
    assert url.drivername == "postgresql"
    assert url.host == "localhost"


def test_managed_identity_allows_passwordless_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql://ade_user@contoso.postgres.database.azure.com:5432/ade?sslmode=require"
        ),
        database_auth_mode="managed_identity",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )

    url = make_url(str(settings.database_url))
    assert url.username == "ade_user"
    assert url.password is None
    assert url.host == "contoso.postgres.database.azure.com"
    assert url.port == 5432
    assert url.database == "ade"
