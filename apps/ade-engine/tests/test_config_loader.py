from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ade_engine.config.loader import load_config_runtime
from ade_engine.core.errors import ConfigError


def _clear_import_cache(prefix: str = "ade_config") -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name)


def _write_manifest(pkg_dir: Path, manifest: dict) -> Path:
    manifest_path = pkg_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _bootstrap_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_dir = tmp_path / "ade_config"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_import_cache()
    return pkg_dir


def test_load_config_runtime_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)

    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "name": "Test Config",
        "description": None,
        "script_api_version": 1,
        "columns": {
            "order": ["email"],
            "fields": {
                "email": {
                    "label": "Email",
                    "module": "column_detectors.email",
                    "required": True,
                    "synonyms": ["e-mail"],
                    "type": "string",
                }
            },
        },
        "hooks": {
            "on_run_start": ["hooks.on_run_start"],
            "on_after_extract": [],
            "on_after_mapping": [],
            "on_before_save": [],
            "on_run_end": [],
        },
        "writer": {
            "append_unmapped_columns": True,
            "unmapped_prefix": "raw_",
            "output_sheet": "Normalized",
        },
        "extra": None,
    }
    manifest_path = _write_manifest(pkg_dir, manifest)

    detectors_dir = pkg_dir / "column_detectors"
    detectors_dir.mkdir()
    (detectors_dir / "__init__.py").write_text("")
    (detectors_dir / "email.py").write_text(
        """
def detect_header(*, column_index, header, **_):
    return 0.75


def transform(*, value, **_):
    return value


def validate(*, value, **_):
    return None
"""
    )

    hooks_dir = pkg_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("")
    (hooks_dir / "on_run_start.py").write_text(
        """
def run(*, context, **_):
    return None
"""
    )

    runtime = load_config_runtime(package="ade_config", manifest_path=manifest_path)

    assert runtime.manifest.model.schema == "ade.manifest/v1"
    assert runtime.manifest.columns.order == ["email"]
    assert "email" in runtime.columns
    assert runtime.columns["email"].detectors[0].__name__ == "detect_header"
    assert runtime.hooks  # registry populated per stage


def test_load_config_runtime_missing_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    missing_manifest = pkg_dir / "missing.json"

    with pytest.raises(ConfigError) as excinfo:
        load_config_runtime(package="ade_config", manifest_path=missing_manifest)

    assert "Manifest file not found" in str(excinfo.value)


def test_load_config_runtime_invalid_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, {"schema": "ade.manifest/v1"})

    with pytest.raises(ConfigError) as excinfo:
        load_config_runtime(package="ade_config", manifest_path=manifest_path)

    assert "Manifest validation failed" in str(excinfo.value)


def test_column_module_missing_module_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "script_api_version": 1,
        "columns": {
            "order": ["foo"],
            "fields": {
                "foo": {
                    "label": "Foo",
                    "module": "column_detectors.missing",
                    "required": False,
                    "synonyms": [],
                }
            },
        },
        "hooks": {"on_run_start": [], "on_after_extract": [], "on_after_mapping": [], "on_before_save": [], "on_run_end": []},
        "writer": {"append_unmapped_columns": True, "unmapped_prefix": "raw_"},
    }
    manifest_path = _write_manifest(pkg_dir, manifest)

    with pytest.raises(ConfigError) as excinfo:
        load_config_runtime(package="ade_config", manifest_path=manifest_path)

    assert "Column module" in str(excinfo.value)


def test_detector_signature_must_be_keyword_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "script_api_version": 1,
        "columns": {
            "order": ["foo"],
            "fields": {
                "foo": {
                    "label": "Foo",
                    "module": "column_detectors.foo",
                    "required": False,
                    "synonyms": [],
                }
            },
        },
        "hooks": {"on_run_start": [], "on_after_extract": [], "on_after_mapping": [], "on_before_save": [], "on_run_end": []},
        "writer": {"append_unmapped_columns": True, "unmapped_prefix": "raw_"},
    }
    manifest_path = _write_manifest(pkg_dir, manifest)

    detectors_dir = pkg_dir / "column_detectors"
    detectors_dir.mkdir()
    (detectors_dir / "__init__.py").write_text("")
    (detectors_dir / "foo.py").write_text(
        """
def detect_header(header):
    return 0.0
"""
    )

    with pytest.raises(ConfigError) as excinfo:
        load_config_runtime(package="ade_config", manifest_path=manifest_path)

    assert "keyword-only" in str(excinfo.value)
