from __future__ import annotations

from pathlib import Path
import os

os.environ.setdefault(
    "ADE_DATABASE_URL",
    "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
)

import pytest


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        path = Path(str(item.fspath))
        path_str = str(path)
        if "/tests/integration/" in path_str:
            item.add_marker(pytest.mark.integration)
        elif "/tests/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
