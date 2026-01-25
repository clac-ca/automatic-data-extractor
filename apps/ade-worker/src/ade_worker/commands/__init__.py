"""Command registrations for ADE worker CLI."""

from __future__ import annotations

import typer

from . import lint
from . import run
from . import tests

COMMAND_MODULES = (
    run,
    tests,
    lint,
)


def register_all(app: typer.Typer) -> None:
    for module in COMMAND_MODULES:
        module.register(app)
