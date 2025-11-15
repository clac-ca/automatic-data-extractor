import textwrap
import textwrap
from pathlib import Path

import pytest

from ade_schemas.manifest import ColumnMeta

from ade_engine.pipeline.registry import ColumnRegistry, ColumnRegistryError


def _write_module(root: Path, path: str, content: str) -> None:
    file_path = root / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_column_registry_loads_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_root = tmp_path / "cfg"
    module_root = pkg_root / "ade_config"
    (module_root / "__init__.py").write_text("", encoding="utf-8")
    _write_module(
        module_root,
        "column_detectors/member.py",
        """
        def detect_from_header(**kwargs):
            return {"scores": {kwargs["field_name"]: 1.0}}

        def transform(*, value, row, field_name, **_):
            row[field_name] = value
            return {field_name: value}

        def validate(*, value, field_name, row_index, **_):
            if not value:
                return [{"code": "missing", "row_index": row_index, "field": field_name}]
            return []
        """,
    )

    monkeypatch.syspath_prepend(str(pkg_root))
    registry = ColumnRegistry(
        {"member": ColumnMeta(label="Member", script="column_detectors/member.py")},
        package="ade_config",
    )

    module = registry.get("member")
    assert module is not None
    assert module.detectors
    assert callable(module.transformer)
    assert callable(module.validator)


def test_column_registry_validates_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_root = tmp_path / "cfg"
    module_root = pkg_root / "ade_config"
    (module_root / "__init__.py").write_text("", encoding="utf-8")
    _write_module(
        module_root,
        "column_detectors/member.py",
        """
        def detect_from_header(header):
            return {"scores": {}}

        def transform(value):
            return value
        """,
    )

    monkeypatch.syspath_prepend(str(pkg_root))

    with pytest.raises(ColumnRegistryError) as excinfo:
        ColumnRegistry(
            {"member": ColumnMeta(label="Member", script="column_detectors/member.py")},
            package="ade_config",
        )

    assert 'Transformer for field' in str(excinfo.value)
