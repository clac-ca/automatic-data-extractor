"""Module entrypoint for ``python -m ade_db`` CLI usage."""

from ade_cli.db import app as cli_app
from ade_cli.local_dev import load_local_env


def main() -> None:
    load_local_env()
    cli_app()

if __name__ == "__main__":
    main()
