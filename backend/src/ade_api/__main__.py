"""Module entrypoint for ``python -m ade_api`` CLI usage."""

from ade_cli.api import app as cli_app


def main() -> None:
    cli_app()

if __name__ == "__main__":
    main()
