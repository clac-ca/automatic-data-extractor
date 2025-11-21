"""Command registrations for the ADE CLI."""

from __future__ import annotations

import typer

from . import build
from . import ci
from . import clean_reset
from . import copy_code
from . import dev
from . import docker
from . import lint_cmd
from . import migrate
from . import routes
from . import setup
from . import start
from . import tests
from . import types_cmd
from . import workpackage

COMMAND_MODULES = (
    setup,
    dev,
    start,
    build,
    tests,
    lint_cmd,
    copy_code,
    types_cmd,
    migrate,
    routes,
    docker,
    clean_reset,
    ci,
    workpackage,
)


def register_all(app: typer.Typer) -> None:
    for module in COMMAND_MODULES:
        module.register(app)
