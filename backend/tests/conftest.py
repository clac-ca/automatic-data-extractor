"""Shared testing fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager

import pytest
from fastapi.testclient import TestClient

@contextmanager
def _test_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database_url: str,
    documents_dir: Path,
) -> Iterator[TestClient]:
    """Instantiate a TestClient using the provided database configuration."""

    monkeypatch.setenv("ADE_DATABASE_URL", database_url)
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))

    import backend.app.config as config_module
    config_module.reset_settings_cache()

    import backend.app.db as db_module
    db_module.reset_database_state()

    import backend.app.main as main_module

    try:
        with TestClient(main_module.app) as client:
            yield client
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()


@pytest.fixture
def app_client(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, Path, Path]]:
    """Return a TestClient bound to an isolated SQLite database."""

    db_path = tmp_path / "ade.sqlite"
    documents_dir = tmp_path / "documents"
    database_url = f"sqlite:///{db_path}"

    with _test_client(monkeypatch, database_url=database_url, documents_dir=documents_dir) as client:
        yield client, db_path, documents_dir


@pytest.fixture
def app_client_factory(
    monkeypatch,
) -> Callable[[str, Path], ContextManager[TestClient]]:
    """Provide a factory that yields TestClients with custom database URLs."""

    def _factory(database_url: str, documents_dir: Path) -> ContextManager[TestClient]:
        return _test_client(monkeypatch, database_url=database_url, documents_dir=documents_dir)

    return _factory
