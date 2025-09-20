"""Tests for Alembic migration helpers."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.app import config as config_module
from backend.app import db as db_module
from backend.app.db_migrations import apply_migrations, ensure_schema


def test_settings_derive_from_data_dir(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "ade-data"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)
    monkeypatch.delenv("ADE_AUTO_MIGRATE", raising=False)

    config_module.reset_settings_cache()
    try:
        settings = config_module.get_settings()
        assert settings.data_dir == data_dir
        assert settings.documents_dir == data_dir / "documents"
        expected_db = data_dir / "db" / "ade.sqlite"
        assert settings.database_url == f"sqlite:///{expected_db}"
        assert settings.database_path == expected_db
    finally:
        config_module.reset_settings_cache()


def _list_tables() -> set[str]:
    engine = db_module.get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
    return {row[0] for row in rows}


def test_ensure_schema_runs_migrations_for_sqlite_file(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)

    config_module.reset_settings_cache()
    db_module.reset_database_state()
    try:
        result = ensure_schema()
        assert result == "migrated"

        second = ensure_schema()
        assert second == "up_to_date"

        database_path = config_module.get_settings().database_path
        assert database_path is not None
        assert database_path.exists()

        tables = _list_tables()
        assert "alembic_version" in tables
        assert "users" in tables
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()


def test_ensure_schema_falls_back_for_in_memory(monkeypatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("ADE_DATA_DIR", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)
    monkeypatch.delenv("ADE_AUTO_MIGRATE", raising=False)

    config_module.reset_settings_cache()
    db_module.reset_database_state()
    try:
        result = ensure_schema()
        assert result == "metadata_created"
        tables = _list_tables()
        assert "alembic_version" not in tables
        assert "users" in tables
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()


def test_ensure_schema_requires_manual_upgrade_when_disabled(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "ade-data"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ADE_AUTO_MIGRATE", "false")
    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)

    config_module.reset_settings_cache()
    db_module.reset_database_state()
    try:
        with pytest.raises(RuntimeError):
            ensure_schema()

        apply_migrations()

        state = ensure_schema()
        assert state == "up_to_date"
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()
