"""Command registrations for the ADE CLI."""

from __future__ import annotations

import typer

from . import build
from . import bundle
from . import ci
from . import clean_reset
from . import dev
from . import docker
from . import lint_cmd
from . import setup
from . import start
from . import tests
PROJECT_COMMAND_MODULES = (
    setup,
    dev,
    start,
    build,
    tests,
    lint_cmd,
    bundle,
    docker,
    clean_reset,
    ci,
)


def register_project(app: typer.Typer) -> None:
    for module in PROJECT_COMMAND_MODULES:
        module.register(app)


def register_all(app: typer.Typer) -> None:
    register_project(app)
