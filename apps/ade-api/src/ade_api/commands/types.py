"""OpenAPI types generation for ADE API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.commands import common


def run_types() -> None:
    """Generate OpenAPI JSON and TypeScript types into apps/ade-web/src/types/generated/openapi.d.ts."""

    openapi_path = Path(__file__).resolve().parents[1] / "openapi.json"
    output_path = common.FRONTEND_DIR / "src" / "types" / "generated" / "openapi.d.ts"

    common.run([sys.executable, "-m", "ade_api.scripts.generate_openapi", "--output", str(openapi_path)])

    if not common.FRONTEND_DIR.exists():
        typer.echo("ℹ️  frontend missing; OpenAPI JSON generated only.")
        raise typer.Exit(code=0)

    common.ensure_node_modules()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    common.require_command(
        npx_cmd,
        friendly_name="npx",
        fix_hint="Install Node.js (LTS) and run `npm install` in apps/ade-web.",
    )
    common.run(
        [
            npx_cmd,
            "openapi-typescript",
            str(openapi_path),
            "--output",
            str(output_path),
            "--export-type",
        ],
        cwd=common.FRONTEND_DIR,
    )
    typer.echo(f"✅ generated {output_path.relative_to(common.REPO_ROOT)}")


def register(app: typer.Typer) -> None:
    def _register(name: str, *, hidden: bool = False) -> None:
        @app.command(name=name, help=run_types.__doc__, hidden=hidden)
        def _types() -> None:
            run_types()

    _register("types")
    _register("openapi-types", hidden=True)
