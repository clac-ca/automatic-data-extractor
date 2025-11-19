"""Command registrations for the ADE CLI."""

from __future__ import annotations

import typer

from . import build
from . import clean_reset
from . import dev
from . import docker
from . import lint_cmd
from . import migrate
from . import setup
from . import start
from . import tests
from . import types_cmd

COMMAND_MODULES = (
    setup,
    dev,
    start,
    build,
    tests,
    lint_cmd,
    types_cmd,
    migrate,
    docker,
    clean_reset,
)


def register_all(app: typer.Typer) -> None:
    for module in COMMAND_MODULES:
        module.register(app)
