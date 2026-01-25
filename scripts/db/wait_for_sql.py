#!/usr/bin/env python
"""Wait for SQL Server to accept connections."""

from __future__ import annotations

import os
import time

from sqlalchemy.engine import make_url

from ade_api.db import build_engine
from ade_api.settings import Settings


def _admin_settings(settings: Settings) -> Settings:
    url = make_url(settings.database_url).set(database="master")
    return settings.model_copy(update={"database_url_override": url.render_as_string(hide_password=False)})


def main() -> None:
    timeout_s = int(os.getenv("ADE_SQL_WAIT_TIMEOUT", "120"))
    settings = Settings()
    admin_settings = _admin_settings(settings)
    engine = build_engine(admin_settings)
    deadline = time.time() + timeout_s
    last_err: Exception | None = None

    try:
        while time.time() < deadline:
            try:
                with engine.connect() as conn:
                    conn.exec_driver_sql("SELECT 1")
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(2)
    finally:
        engine.dispose()

    raise SystemExit(f"SQL Server not ready after {timeout_s}s. Last error: {last_err!r}")


if __name__ == "__main__":
    main()
