"""CLI to generate the backend OpenAPI schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..main import create_app

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_OUTPUT = REPO_ROOT / "apps" / "ade-api" / "src" / "ade_api" / "openapi.json"


def _write_schema(path: Path, schema: dict, indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(schema, handle, indent=indent)
        if indent:
            handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render OpenAPI schema using the FastAPI application.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to write the JSON schema (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Pretty-print indentation (set to 0 for compact output).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Alias for --indent 0 (minifies the output).",
    )
    args = parser.parse_args(argv)

    indent = 0 if args.compact else max(args.indent, 0)
    schema = create_app().openapi()
    output_path = args.output.expanduser().resolve()
    _write_schema(output_path, schema, indent or None)
    print(f"📝 wrote OpenAPI schema to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
