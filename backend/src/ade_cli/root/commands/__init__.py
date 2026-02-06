"""Root `ade` command registration."""

from __future__ import annotations

import typer

from . import api, db, dev, reset, restart, start, status, stop, storage, test, web, worker


def register_all(app: typer.Typer) -> None:
    for module in (
        api,
        db,
        dev,
        reset,
        restart,
        start,
        status,
        stop,
        storage,
        test,
        web,
        worker,
    ):
        module.register(app)
