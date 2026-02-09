"""Module entrypoint for ``python -m ade_cli``."""

from .local_dev import load_local_env
from .main import app as cli_app


def main() -> None:
    load_local_env()
    cli_app()

if __name__ == "__main__":
    main()
