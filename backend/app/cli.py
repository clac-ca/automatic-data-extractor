"""Command-line interface entrypoint for ADE utilities."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable

from .services import auth as auth_service

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ADE command-line utilities")
    subparsers = parser.add_subparsers(dest="group", required=True)
    auth_service.register_cli(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    handler: Callable[[argparse.Namespace], int] | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except ValueError as exc:
        logger.error(str(exc))
        return 1
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("ADE CLI command failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
