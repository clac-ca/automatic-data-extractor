"""Module execution entrypoint for ``python -m cli``."""

from cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
