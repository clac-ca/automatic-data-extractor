"""Module entrypoint for ``python -m ade_cli``."""

from .main import app as cli_app


def main() -> None:
    cli_app()

if __name__ == "__main__":
    main()
