"""Module entrypoint for ``python -m ade_storage`` CLI usage."""

from ade_cli.storage import app as cli_app


def main() -> None:
    cli_app()

if __name__ == "__main__":
    main()
