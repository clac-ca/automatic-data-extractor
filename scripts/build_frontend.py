"""Copy the compiled React assets into ``ade/web``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ade.main import (
    DEFAULT_FRONTEND_DIR,
    FRONTEND_BUILD_DIRNAME,
    WEB_DIR,
    sync_frontend_assets,
)

DEFAULT_DIST = DEFAULT_FRONTEND_DIR / FRONTEND_BUILD_DIRNAME
DEFAULT_STATIC = WEB_DIR


def copy_frontend_build(src: Path, dest: Path) -> None:
    """Mirror ``src`` contents into ``dest`` using the application helper."""

    sync_frontend_assets(src, dest)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy frontend/dist assets into ade/web for packaging.",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help="Path to the compiled frontend distribution directory.",
    )
    parser.add_argument(
        "--static",
        type=Path,
        default=DEFAULT_STATIC,
        help="Destination static directory inside the ade package.",
    )
    args = parser.parse_args()
    copy_frontend_build(args.dist, args.static)
    print(f"Copied frontend assets from {args.dist} to {args.static}.")


if __name__ == "__main__":
    main()
