"""Console script entrypoint for the ADE CLI."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence

from fastapi import HTTPException

from .app import build_cli_app

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

Handler = Callable[[argparse.Namespace], object | None]

__all__ = ["main"]


def _format_http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    if detail is None:
        return exc.status_code and f"HTTP {exc.status_code}" or "HTTP error"
    return str(detail)


def _emit_error(message: str) -> None:
    """Write ``message`` to stderr with a consistent prefix."""

    print(f"Error: {message}", file=sys.stderr)


def _run_handler(handler: Handler, args: argparse.Namespace) -> None:
    """Execute ``handler`` and await it when it returns a coroutine."""

    result = handler(args)
    if asyncio.iscoroutine(result):
        asyncio.run(result)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI and return an exit code."""

    # Build the parser and process CLI input.
    parser = build_cli_app()
    args = parser.parse_args(argv)

    # Each subcommand attaches a handler; fall back to help when missing.
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_FAILURE

    try:
        _run_handler(handler, args)
    except HTTPException as exc:
        _emit_error(_format_http_detail(exc))
        return EXIT_FAILURE
    except ValueError as exc:
        _emit_error(str(exc))
        return EXIT_FAILURE
    except KeyboardInterrupt:
        _emit_error("Aborted")
        return EXIT_FAILURE
    except Exception as exc:  # pragma: no cover - defensive catch-all
        _emit_error(f"Unexpected error: {exc}")
        return EXIT_FAILURE

    return EXIT_SUCCESS


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
