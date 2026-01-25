from __future__ import annotations

from fastapi import FastAPI
import pytest

from ade_api.db import get_engine, get_sessionmaker_from_app, init_db, shutdown_db
from ade_api.settings import Settings


def test_init_shutdown_db_state() -> None:
    pytest.importorskip("pyodbc")
    app = FastAPI()
    settings = Settings(
        _env_file=None,
        database_url_override=(
            "mssql+pyodbc://user:pass@localhost:1433/ade"
            "?driver=ODBC+Driver+18+for+SQL+Server"
        ),
    )

    init_db(app, settings)
    assert get_engine(app) is not None
    assert get_sessionmaker_from_app(app) is not None

    shutdown_db(app)
    assert getattr(app.state, "db_engine") is None
    assert getattr(app.state, "db_sessionmaker") is None
