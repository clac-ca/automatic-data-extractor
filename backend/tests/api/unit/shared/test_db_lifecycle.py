from __future__ import annotations

from fastapi import FastAPI

from ade_api.db import get_engine_from_app, get_session_factory_from_app, init_db, shutdown_db
from ade_api.settings import Settings


def test_init_shutdown_db_state() -> None:
    app = FastAPI()
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )

    init_db(app, settings)
    assert get_engine_from_app(app) is not None
    assert get_session_factory_from_app(app) is not None

    shutdown_db(app)
    assert getattr(app.state, "db_engine") is None
    assert getattr(app.state, "db_sessionmaker") is None
