"""Shared testing fixtures."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.email import canonicalize_email
from backend.app.services.auth import hash_password
from backend.app.db import get_sessionmaker
from backend.app.models import Event, User, UserRole

DEFAULT_USER_EMAIL = "admin@example.com"
DEFAULT_USER_PASSWORD = "password123"


def _seed_default_user() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        existing = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one_or_none()
        )
        if existing is not None:
            return
        user = User(
            email=DEFAULT_USER_EMAIL,
            password_hash=hash_password(DEFAULT_USER_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()

@contextmanager
def _test_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database_url: str | None = None,
    documents_dir: Path | None = None,
    data_dir: Path | None = None,
) -> Iterator[TestClient]:
    """Instantiate a TestClient using the provided database configuration."""

    if data_dir is not None:
        monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    else:
        monkeypatch.delenv("ADE_DATA_DIR", raising=False)

    if database_url is not None:
        monkeypatch.setenv("ADE_DATABASE_URL", database_url)
    else:
        monkeypatch.delenv("ADE_DATABASE_URL", raising=False)

    if documents_dir is not None:
        monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))
    else:
        monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)
    if "ADE_PURGE_SCHEDULE_ENABLED" not in os.environ:
        monkeypatch.setenv("ADE_PURGE_SCHEDULE_ENABLED", "0")
    if "ADE_PURGE_SCHEDULE_RUN_ON_STARTUP" not in os.environ:
        monkeypatch.setenv("ADE_PURGE_SCHEDULE_RUN_ON_STARTUP", "0")
    if "ADE_JWT_SECRET_KEY" not in os.environ:
        monkeypatch.setenv("ADE_JWT_SECRET_KEY", "insecure-test-secret")

    import backend.app.config as config_module
    config_module.reset_settings_cache()

    import backend.app.db as db_module
    db_module.reset_database_state()

    import backend.app.services.auth as auth_module
    auth_module.clear_caches()

    import backend.app.main as main_module

    try:
        with TestClient(main_module.app, follow_redirects=False) as client:
            _seed_default_user()
            settings = config_module.get_settings()
            if settings.auth_disabled:
                client.headers.pop("Authorization", None)
            else:
                login_response = client.post(
                    "/auth/token",
                    data={
                        "username": DEFAULT_USER_EMAIL,
                        "password": DEFAULT_USER_PASSWORD,
                    },
                )
                assert login_response.status_code == 200, login_response.text
                token = login_response.json()["access_token"]
                client.headers.update({"Authorization": f"Bearer {token}"})
            session_factory = get_sessionmaker()
            with session_factory() as db:
                db.query(Event).delete()
                db.commit()
            yield client
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()


@pytest.fixture
def app_client(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, Path, Path]]:
    """Return a TestClient bound to an isolated SQLite database."""

    data_dir = tmp_path / "data"
    db_path = data_dir / "db" / "ade.sqlite"
    documents_dir = data_dir / "documents"

    with _test_client(monkeypatch, data_dir=data_dir) as client:
        yield client, db_path, documents_dir


@pytest.fixture
def app_client_factory(
    monkeypatch,
) -> Callable[[str | None, Path | None], ContextManager[TestClient]]:
    """Provide a factory that yields TestClients with custom database URLs."""

    def _factory(
        database_url: str | None,
        documents_dir: Path | None,
        *,
        data_dir: Path | None = None,
    ) -> ContextManager[TestClient]:
        return _test_client(
            monkeypatch,
            database_url=database_url,
            documents_dir=documents_dir,
            data_dir=data_dir,
        )

    return _factory
