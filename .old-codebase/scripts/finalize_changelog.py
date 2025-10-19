#!/usr/bin/env python3
"""Promote the Unreleased changelog section to a tagged release.

The script reads ``CHANGELOG.md`` in Keep a Changelog format, moves the
"Unreleased" section under a new ``vX.Y.Z`` heading, and restores a stub
Unreleased template for future entries. The release version defaults to the
``project.version`` field in ``pyproject.toml``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

try:  # Python 3.12+
    import tomllib  # type: ignore[attr-define]
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise SystemExit(
            "Python 3.12+ or the 'tomli' package is required to parse pyproject.toml"
        ) from exc

CHANGELOG_PATH = Path("CHANGELOG.md")
PYPROJECT_PATH = Path("pyproject.toml")
UNRELEASED_TEMPLATE = (
    "## [Unreleased]\n\n"
    "### Added\n"
    "- Placeholder for upcoming changes.\n\n"
)
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def read_project_version() -> str:
    if not PYPROJECT_PATH.is_file():
        raise SystemExit("pyproject.toml is required but was not found")

    with PYPROJECT_PATH.open("rb") as fh:
        data = tomllib.load(fh)

    version = data.get("project", {}).get("version")
    if not version:
        raise SystemExit("project.version is required in pyproject.toml")

    return version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert the changelog's Unreleased section into a tagged release."
    )
    parser.add_argument(
        "--version",
        help="Release version (defaults to project.version)",
    )
    parser.add_argument(
        "--date",
        help="Release date in YYYY-MM-DD (defaults to today in UTC)",
    )
    return parser.parse_args()


def ensure_semver(version: str) -> str:
    raw = version.lstrip("v")
    if not SEMVER_RE.fullmatch(raw):
        raise SystemExit(f"{version!r} is not a valid semantic version")
    return f"v{raw}"


def read_unreleased_block(changelog: str) -> tuple[str, str, str]:
    pattern = re.compile(r"## \[Unreleased\]\n(?P<body>.*?)(?=\n## \[|\Z)", re.S)
    match = pattern.search(changelog)
    if not match:
        raise SystemExit("Could not find an '## [Unreleased]' section in CHANGELOG.md")

    start, end = match.span()
    body = match.group("body").strip("\n")
    before = changelog[:start]
    after = changelog[end:]
    return before, body, after


def main() -> None:
    args = parse_args()
    version = ensure_semver(args.version or read_project_version())

    if args.date:
        try:
            release_date = dt.date.fromisoformat(args.date)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise SystemExit(f"Invalid date {args.date!r}: {exc}")
    else:
        release_date = dt.datetime.utcnow().date()

    if not CHANGELOG_PATH.is_file():
        raise SystemExit("CHANGELOG.md does not exist")

    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    before, body, after = read_unreleased_block(changelog_text)

    release_body = body.strip()
    if not release_body or release_body == "### Added\n- Placeholder for upcoming changes.":
        release_body = "_No notable changes._"

    release_section = (
        f"## [{version}] - {release_date.isoformat()}\n\n"
        f"{release_body.rstrip()}\n\n"
    )

    updated = before + UNRELEASED_TEMPLATE + release_section + after.lstrip("\n")
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")
    print(f"Promoted Unreleased to {version} ({release_date.isoformat()})")


if __name__ == "__main__":
    main()
