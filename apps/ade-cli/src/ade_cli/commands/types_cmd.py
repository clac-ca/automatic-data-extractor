"""Types generation command."""

from __future__ import annotations

import os
import sys

import typer

from ade_cli.commands import common


def run_types() -> None:
    """Generate OpenAPI JSON and TypeScript types into apps/ade-web/src/types/generated/openapi.d.ts."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    openapi_path = common.BACKEND_SRC / "openapi.json"
    output_path = common.FRONTEND_DIR / "src" / "types" / "generated" / "openapi.d.ts"

    common.run(
        [sys.executable, "-m", "ade_api.scripts.generate_openapi", "--output", str(openapi_path)]
    )

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

    _register("openapi-types")
    _register("types", hidden=True)
