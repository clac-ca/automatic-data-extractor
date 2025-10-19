"""Module execution entrypoint for ``python -m ade.cli``."""

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
