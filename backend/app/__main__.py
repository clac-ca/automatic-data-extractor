"""Execute ADE command-line utilities via ``python -m backend.app``."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
