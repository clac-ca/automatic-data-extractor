from __future__ import annotations

from ade_db.migrations_runner import alembic_config
from ade_db.settings import Settings, get_settings, reload_settings


def test_db_settings_require_only_database_fields() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade",
    )

    assert str(settings.database_url).startswith("postgresql+psycopg://")
    assert settings.database_pool_size == 5


def test_alembic_config_defaults_to_db_settings(monkeypatch) -> None:
    monkeypatch.setenv(
        "ADE_DATABASE_URL",
        "postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
    )
    reload_settings()

    try:
        with alembic_config() as cfg:
            settings = cfg.attributes["settings"]
            assert isinstance(settings, Settings)
            assert settings.database_url
    finally:
        reload_settings()


def test_db_settings_accessors_cache(monkeypatch) -> None:
    monkeypatch.setenv(
        "ADE_DATABASE_URL",
        "postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
    )
    first = get_settings()
    second = get_settings()

    assert first is second
