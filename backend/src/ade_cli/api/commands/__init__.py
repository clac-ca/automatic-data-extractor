"""ADE API command registration."""

from __future__ import annotations

import typer

from . import dev, lint, routes, start, test, types, users


def register_all(app: typer.Typer) -> None:
    for module in (
        dev,
        lint,
        routes,
        start,
        test,
        types,
        users,
    ):
        module.register(app)
