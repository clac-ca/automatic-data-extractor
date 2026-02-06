from __future__ import annotations

from ade_common.paths import SRC_ROOT

DISALLOWED_PATTERNS = (
    "sqlalchemy.ext.asyncio",
    "create_async_engine",
)


def test_no_async_sqlalchemy_imports_in_runtime() -> None:
    root = SRC_ROOT / "ade_api"
    assert root.is_dir(), f"Runtime source directory missing: {root}"
    for path in root.rglob("*.py"):
        contents = path.read_text(encoding="utf-8")
        for pattern in DISALLOWED_PATTERNS:
            assert pattern not in contents, f"{pattern} found in {path}"
