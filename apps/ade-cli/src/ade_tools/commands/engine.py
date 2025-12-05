"""Expose the ade_engine CLI under `ade engine` (full help/flags preserved)."""

from __future__ import annotations

import typer

from ade_tools.commands import common


def register(app: typer.Typer) -> None:
    """Mount the ade_engine Typer app as a subcommand for discovery/help."""

    common.refresh_paths()
    common.require_python_module(
        "ade_engine",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine`).",
    )

    # Import lazily so the module check above can provide a friendly error.
    from ade_engine.cli.app import app as engine_app  # type: ignore

    app.add_typer(
        engine_app,
        name="engine",
        help="ADE engine runtime CLI (mirrors `python -m ade_engine`).",
    )


__all__ = ["register"]
