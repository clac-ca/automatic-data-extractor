from __future__ import annotations

from pathlib import Path

DISALLOWED_PATTERNS = (
    "sqlalchemy.ext.asyncio",
    "create_async_engine",
)


def test_no_async_sqlalchemy_imports_in_runtime() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "ade_api"
    for path in root.rglob("*.py"):
        contents = path.read_text(encoding="utf-8")
        for pattern in DISALLOWED_PATTERNS:
            assert pattern not in contents, f"{pattern} found in {path}"
