"""Console script entrypoint for the ADE CLI."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence

from fastapi import HTTPException

from .app import build_cli_app

__all__ = ["main"]


def _format_http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    if detail is None:
        return exc.status_code and f"HTTP {exc.status_code}" or "HTTP error"
    return str(detail)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI and return an exit code."""

    parser = build_cli_app()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    try:
        result = handler(args)
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except HTTPException as exc:
        message = _format_http_detail(exc)
        print(f"Error: {message}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Aborted", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch-all
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
