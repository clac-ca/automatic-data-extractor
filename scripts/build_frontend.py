"""Copy the compiled React assets into ``app/static``."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = PROJECT_ROOT / "frontend" / "dist"
DEFAULT_STATIC = PROJECT_ROOT / "app" / "static"


def _clean_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for entry in path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def copy_frontend_build(src: Path, dest: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Frontend build directory not found at {src}")
    if not src.is_dir():
        raise NotADirectoryError(f"Frontend build path {src} is not a directory")
    _clean_directory(dest)
    shutil.copytree(src, dest, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy frontend/dist assets into app/static for packaging.",
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
        help="Destination static directory inside the app package.",
    )
    args = parser.parse_args()
    copy_frontend_build(args.dist, args.static)
    print(f"Copied frontend assets from {args.dist} to {args.static}.")


if __name__ == "__main__":
    main()
