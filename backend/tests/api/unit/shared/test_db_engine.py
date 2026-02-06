import pytest

from ade_api.settings import Settings
from ade_db.engine import build_engine


def test_build_engine_allows_managed_identity_passwordless_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user@contoso.postgres.database.azure.com:5432/ade?sslmode=require",
        database_auth_mode="managed_identity",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )

    engine = build_engine(settings)
    try:
        url = engine.url
        assert url.username == "user"
        assert url.password is None
    finally:
        engine.dispose()


def test_build_engine_normalizes_postgres_driver() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:secret@contoso.postgres.database.azure.com:5432/ade",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )
    engine = build_engine(settings)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_settings_rejects_non_postgres_urls() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            database_url="sqlite:///tmp/test.db",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
