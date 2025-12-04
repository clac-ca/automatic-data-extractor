from __future__ import annotations

import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from ade_engine.schemas.manifest import ColumnsConfig, FieldConfig, HookCollection, ManifestV1, WriterConfig


@dataclass
class ConfigPaths:
    package_dir: Path
    manifest_path: Path


def clear_config_import(prefix: str = "ade_config") -> None:
    """Drop cached config modules to allow clean imports per test."""

    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name)


def bootstrap_config_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    package_dir = tmp_path / "ade_config"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    clear_config_import()
    return package_dir


def _write_row_detectors(package_dir: Path) -> None:
    detectors = package_dir / "row_detectors"
    detectors.mkdir()
    (detectors / "__init__.py").write_text("")
    (detectors / "basic.py").write_text(
        textwrap.dedent(
            """
            def detect_header(*, row_index, logger, event_emitter, **_):
                return {"scores": {"header": 1.0 if row_index == 1 else 0.0, "data": 1.0 if row_index > 1 else 0.0}}
            """
        )
    )


def _write_column_module(
    package_dir: Path,
    *,
    field: str,
    header: str,
    include_transform: bool = False,
    include_validator: bool = False,
) -> None:
    detectors = package_dir / "column_detectors"
    detectors.mkdir(exist_ok=True)
    (detectors / "__init__.py").write_text("")

    body = [
        "def detect_header(*, header, logger=None, event_emitter=None, **_):",
        "    return 1.0 if (header or '').strip().lower() == '%s' else 0.0" % header.lower(),
    ]

    if include_transform:
        body.extend(
            [
                "",
                "def transform(*, value, row, logger=None, event_emitter=None, **_):",
                "    if value is None:",
                "        return None",
                "    row['%s'] = str(value).strip().title()" % field,
                "    return {'%s': row['%s']}" % (field, field),
            ]
        )

    if include_validator:
        body.extend(
            [
                "",
                "def validate(*, value, logger=None, event_emitter=None, **_):",
                "    if value in (None, ''):",
                "        return [{'code': 'missing_value', 'severity': 'error', 'message': '%s is required'}]" % field,
                "    return []",
            ]
        )

    module_path = detectors / f"{field}.py"
    module_path.write_text("\n".join(body) + "\n")


def _write_hooks(package_dir: Path, *, failing: bool) -> None:
    hooks = package_dir / "hooks"
    hooks.mkdir()
    (hooks / "__init__.py").write_text("")
    if failing:
        (hooks / "failing.py").write_text(
            textwrap.dedent(
                """
                def run(*, logger, event_emitter, **__):
                    raise RuntimeError("hook boom")
                """
            )
        )
    else:
        (hooks / "notes.py").write_text(
            textwrap.dedent(
                """
                def run(*, logger, event_emitter, **_):
                    logger.info("hook ran")
                    event_emitter.custom("hook.note", status="ok")
                """
            )
        )


def _write_manifest(
    package_dir: Path,
    *,
    fields: list[tuple[str, str]],
    include_hooks: bool,
    failing_hook: bool,
) -> Path:
    manifest = ManifestV1(
        schema="ade.manifest/v1",
        version="1.0.0",
        name="Fixture Config",
        description="minimal config for engine tests",
        script_api_version=3,
        columns=ColumnsConfig(
            order=[field for field, _ in fields],
            fields={
                field: FieldConfig(label=field.title(), module=f"column_detectors.{field}", required=True, synonyms=[], type="string")
                for field, _ in fields
            },
        ),
        hooks=HookCollection(
            on_run_start=["hooks.failing" if failing_hook else "hooks.notes"] if include_hooks else [],
            on_after_extract=[],
            on_after_mapping=[],
            on_before_save=[],
            on_run_end=[],
        ),
        writer=WriterConfig(append_unmapped_columns=True, unmapped_prefix="raw_", output_sheet="Normalized"),
        extra=None,
    )

    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(json.dumps(json.loads(manifest.model_dump_json())))
    return manifest_path


def make_minimal_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_transform: bool = False,
    include_validator: bool = False,
    include_hooks: bool = False,
    failing_hook: bool = False,
) -> ConfigPaths:
    """Create an importable temporary `ade_config` with basic detectors."""

    package_dir = bootstrap_config_package(tmp_path, monkeypatch)
    _write_row_detectors(package_dir)

    fields = [("member_id", "member_id"), ("value", "value")]
    _write_column_module(
        package_dir,
        field="member_id",
        header="member_id",
        include_transform=include_transform,
        include_validator=include_validator,
    )
    _write_column_module(package_dir, field="value", header="value", include_transform=False, include_validator=False)

    if include_hooks:
        _write_hooks(package_dir, failing=failing_hook)
    manifest_path = _write_manifest(
        package_dir,
        fields=fields,
        include_hooks=include_hooks,
        failing_hook=failing_hook,
    )

    return ConfigPaths(package_dir=package_dir, manifest_path=manifest_path)
