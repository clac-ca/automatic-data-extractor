from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        path = Path(str(item.fspath))
        path_str = str(path)
        if "/tests/integration/" in path_str:
            item.add_marker(pytest.mark.integration)
        elif "/tests/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
