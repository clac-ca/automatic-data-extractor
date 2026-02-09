from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        parts = Path(str(item.fspath)).parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "unit" in parts:
            item.add_marker(pytest.mark.unit)
