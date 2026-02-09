from __future__ import annotations

import logging

from ade_api.app import lifecycles
from ade_api.settings import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
        "blob_container": "ade-test",
        "blob_connection_string": "UseDevelopmentStorage=true",
        "secret_key": "test-secret-key-for-tests-please-change",
    }
    values.update(overrides)
    return Settings(**values)


def test_estimate_api_max_db_connections_uses_process_pool_product() -> None:
    settings = _settings(
        api_processes=3,
        database_pool_size=5,
        database_max_overflow=10,
    )

    estimated = lifecycles.estimate_api_max_db_connections(settings)

    assert estimated == 45


def test_log_db_capacity_estimate_warns_when_budget_is_exceeded(caplog) -> None:
    settings = _settings(
        api_processes=4,
        database_pool_size=5,
        database_max_overflow=10,
        database_connection_budget=20,
    )

    with caplog.at_level(logging.INFO, logger="ade_api.app.lifecycles"):
        estimated = lifecycles.log_db_capacity_estimate(settings)

    assert estimated == 60
    assert "db.capacity.estimated" in caplog.text
    assert "db.capacity.budget_exceeded" in caplog.text


def test_log_db_capacity_estimate_does_not_warn_when_budget_is_sufficient(caplog) -> None:
    settings = _settings(
        api_processes=2,
        database_pool_size=5,
        database_max_overflow=10,
        database_connection_budget=40,
    )

    with caplog.at_level(logging.INFO, logger="ade_api.app.lifecycles"):
        estimated = lifecycles.log_db_capacity_estimate(settings)

    assert estimated == 30
    assert "db.capacity.estimated" in caplog.text
    assert "db.capacity.budget_exceeded" not in caplog.text


def test_configure_threadpool_tokens_updates_anyio_limiter(monkeypatch) -> None:
    class _Limiter:
        total_tokens = 10

    limiter = _Limiter()
    monkeypatch.setattr(
        lifecycles.anyio.to_thread,
        "current_default_thread_limiter",
        lambda: limiter,
    )

    previous, current = lifecycles._configure_threadpool_tokens(tokens=64)

    assert previous == 10
    assert current == 64
    assert limiter.total_tokens == 64
