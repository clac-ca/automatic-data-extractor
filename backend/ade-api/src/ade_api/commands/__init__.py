"""Command registrations for ADE API CLI."""

from __future__ import annotations

import typer

from . import lint, routes, server, tests, types, users

COMMAND_MODULES = (
    server,
    tests,
    lint,
    routes,
    types,
    users,
)


def register_all(app: typer.Typer) -> None:
    for module in COMMAND_MODULES:
        module.register(app)
