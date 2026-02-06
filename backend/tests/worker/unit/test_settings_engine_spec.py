from __future__ import annotations

import pytest

from ade_worker.settings import Settings


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ADE_DATABASE_URL",
        "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
    )
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")


def test_worker_engine_spec_defaults_to_pinned_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.engine_spec.endswith("@v1.7.9")


def test_worker_engine_spec_prefers_canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_ENGINE_SPEC", "ade-engine @ git+https://example.com/engine@v9.9.9")

    settings = Settings(_env_file=None)

    assert settings.engine_spec == "ade-engine @ git+https://example.com/engine@v9.9.9"
