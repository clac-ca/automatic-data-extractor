"""`ade-engine version` command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from ade_engine import __version__
from ade_engine.schemas.manifest import ManifestV1


def version_command(manifest_path: Optional[Path] = typer.Option(None, "--manifest-path")) -> None:
    payload: dict[str, str | None] = {"version": __version__}
    if manifest_path:
        manifest_json = json.loads(Path(manifest_path).read_text())
        manifest = ManifestV1.model_validate(manifest_json)
        payload["manifest_version"] = manifest.version

    typer.echo(json.dumps(payload))


__all__ = ["version_command"]
