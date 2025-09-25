"""Module execution entrypoint for ``python -m backend.cli``."""

from backend.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
