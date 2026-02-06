"""Module entrypoint for ``python -m ade_storage`` CLI usage."""

from ade_cli.local_dev import load_local_env
from ade_cli.storage import app as cli_app


def main() -> None:
    load_local_env()
    cli_app()

if __name__ == "__main__":
    main()
