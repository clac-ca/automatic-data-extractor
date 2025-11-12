"""Entry point for ``python -m ade_engine``."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from . import DEFAULT_METADATA, ManifestNotFoundError, load_config_manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ade_engine",
        description="ADE engine runtime scaffold.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the ade_engine version and exit.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Optional path to an ade_config manifest (defaults to the installed package resource).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 when the CLI completes successfully."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.version:
        print(f"{DEFAULT_METADATA.name} {DEFAULT_METADATA.version}")
        return 0

    try:
        manifest = load_config_manifest(manifest_path=args.manifest_path)
    except ManifestNotFoundError as exc:
        print(f"Manifest error: {exc}")
        return 1

    print(
        json.dumps(
            {
                "engine_version": DEFAULT_METADATA.version,
                "config_manifest": manifest,
            },
            indent=2,
        )
    )
    return 0


def console_entrypoint() -> NoReturn:
    """Console script helper (if ever referenced)."""

    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover - manual execution path
    console_entrypoint()
