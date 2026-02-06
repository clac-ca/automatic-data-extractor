"""OpenAPI types generation for ADE API."""

from __future__ import annotations

import os
import sys

import typer

from .. import shared


def run_types() -> None:
    """Generate OpenAPI JSON and TypeScript types for frontend."""

    openapi_path = shared.REPO_ROOT / "backend" / "src" / "ade_api" / "openapi.json"
    output_path = shared.FRONTEND_DIR / "src" / "types" / "generated" / "openapi.d.ts"

    shared.run(
        [
            sys.executable,
            "-m",
            "ade_api.scripts.generate_openapi",
            "--output",
            str(openapi_path),
        ]
    )

    if not shared.FRONTEND_DIR.exists():
        typer.echo("ℹ️  frontend missing; OpenAPI JSON generated only.")
        raise typer.Exit(code=0)

    shared.ensure_node_modules()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    shared.require_command(
        npx_cmd,
        friendly_name="npx",
        fix_hint="Install Node.js (LTS) and run `npm install` in frontend.",
    )
    shared.run(
        [
            npx_cmd,
            "openapi-typescript",
            str(openapi_path),
            "--output",
            str(output_path),
            "--export-type",
        ],
        cwd=shared.FRONTEND_DIR,
    )
    typer.echo(f"generated {output_path.relative_to(shared.REPO_ROOT)}")


def register(app: typer.Typer) -> None:
    @app.command(name="types", help=run_types.__doc__)
    def _types() -> None:
        run_types()
