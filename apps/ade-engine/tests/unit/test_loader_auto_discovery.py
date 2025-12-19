from __future__ import annotations

from pathlib import Path

from ade_engine.extensions.loader import import_and_register
from ade_engine.extensions.registry import Registry
from ade_engine.models import HookName


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_import_and_register_auto_discovers_plugin_modules(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"

    # Package exists but has no package-level register() entrypoint.
    _write(config_dir / "src" / "my_pkg" / "__init__.py", "")

    # Auto-discovery is convention-first: only columns/, row_detectors/, hooks/.
    _write(config_dir / "src" / "my_pkg" / "utils" / "__init__.py", "")
    _write(
        config_dir / "src" / "my_pkg" / "utils" / "not_a_plugin.py",
        "\n".join(
            [
                "from ade_engine.models import FieldDef",
                "",
                "def register(registry):",
                "    registry.register_field(FieldDef(name='utils_field', label='Utils', dtype='string'))",
                "",
            ]
        ),
    )

    _write(config_dir / "src" / "my_pkg" / "columns" / "__init__.py", "")
    _write(
        config_dir / "src" / "my_pkg" / "columns" / "alpha.py",
        "\n".join(
            [
                "from ade_engine.models import FieldDef",
                "",
                "def register(registry):",
                "    registry.register_field(FieldDef(name='alpha', label='Alpha', dtype='string'))",
                "",
            ]
        ),
    )

    # Skip private modules and tests/.
    _write(
        config_dir / "src" / "my_pkg" / "columns" / "_ignored.py",
        "\n".join(
            [
                "from ade_engine.models import FieldDef",
                "",
                "def register(registry):",
                "    registry.register_field(FieldDef(name='ignored', label='Ignored', dtype='string'))",
                "",
            ]
        ),
    )
    _write(
        config_dir / "src" / "my_pkg" / "columns" / "tests" / "test_should_ignore.py",
        "\n".join(
            [
                "from ade_engine.models import FieldDef",
                "",
                "def register(registry):",
                "    registry.register_field(FieldDef(name='tests_field', label='Tests', dtype='string'))",
                "",
            ]
        ),
    )

    _write(config_dir / "src" / "my_pkg" / "hooks" / "__init__.py", "")
    _write(
        config_dir / "src" / "my_pkg" / "hooks" / "workbook_start.py",
        "\n".join(
            [
                "def on_workbook_start(**_):",
                "    return None",
                "",
                "def register(registry):",
                "    registry.register_hook(on_workbook_start, hook='on_workbook_start', priority=0)",
                "",
            ]
        ),
    )

    registry = Registry()
    module_names = import_and_register(config_dir, registry=registry)
    registry.finalize()

    assert module_names == ["my_pkg.columns.alpha", "my_pkg.hooks.workbook_start"]
    assert sorted(registry.fields.keys()) == ["alpha"]
    assert len(registry.hooks[HookName.ON_WORKBOOK_START]) == 1

