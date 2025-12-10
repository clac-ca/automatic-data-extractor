from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

from ade_engine.registry import Registry, import_all, registry_context


def _ensure_fixture_package_loaded():
    import importlib.util

    pkg_path = FIXTURES / "discovery_pkg"
    spec = importlib.util.spec_from_file_location("discovery_pkg", pkg_path / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["discovery_pkg"] = module
    module.__path__ = [str(pkg_path)]
    assert spec.loader is not None
    spec.loader.exec_module(module)


def test_import_all_imports_all_modules_once():
    if str(FIXTURES) not in sys.path:
        sys.path.insert(0, str(FIXTURES))
    _ensure_fixture_package_loaded()
    reg = Registry()
    with registry_context(reg):
        imported = import_all("discovery_pkg")
    assert imported == sorted(imported)
    # one row detector and one column detector from fixtures
    assert len(reg.row_detectors) == 1
    assert len(reg.column_detectors) == 1


def test_import_all_no_package_path_returns_empty():
    if str(FIXTURES) not in sys.path:
        sys.path.insert(0, str(FIXTURES))
    _ensure_fixture_package_loaded()
    reg = Registry()
    with registry_context(reg):
        imported = import_all("discovery_pkg.a")  # module, not package
    assert imported == []
