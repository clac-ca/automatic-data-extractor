"""Module entrypoint so `python -m ade_cli` works when ade_cli is installed."""

from __future__ import annotations

import sys


def _print_install_help(missing: str) -> None:
    message = (
        f"❌ Missing dependency '{missing}'. Install ADE into an active virtualenv first:\n\n"
        "    pip install -e apps/ade-cli -e apps/ade-api -e apps/ade-worker\n\n"
        "See README: Developer Setup."
    )
    sys.stderr.write(message + "\n")
    sys.exit(1)


def main() -> None:
    try:
        from ade_cli.cli import app  # type: ignore
    except ModuleNotFoundError as exc:
        missing = exc.name or "ade_cli dependencies"
        _print_install_help(missing)

    app()


if __name__ == "__main__":
    main()
