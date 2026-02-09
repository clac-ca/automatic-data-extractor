from __future__ import annotations

import io
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

import ade_api.features.configs.storage as config_storage_module
from ade_api.features.configs.exceptions import ConfigImportError
from ade_api.features.configs.storage import ConfigStorage


def _build_import_archive(
    *,
    wrapper: str = "",
    init_content: str = "__all__ = []\n",
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    archive_bytes = io.BytesIO()
    prefix = f"{wrapper}/" if wrapper else ""
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{prefix}pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr(f"{prefix}src/ade_config/__init__.py", init_content)
        for rel_path, payload in (extra_files or {}).items():
            zf.writestr(f"{prefix}{rel_path}", payload)
    return archive_bytes.getvalue()


def test_templates_materialize_and_load(
    tmp_path: Path,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()
    storage.validate_path = lambda path: ([], "sha256:test")  # type: ignore[method-assign]

    storage.materialize_from_template(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
    )

    config_path = storage.config_path(workspace_id, configuration_id)
    assert (config_path / "src" / "ade_config" / "__init__.py").is_file()
    assert config_path.exists()
    pyproject = (config_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "\"ade-engine\"," in pyproject
    assert "[tool.uv.sources]" in pyproject
    assert "ade-engine = { git = " in pyproject
    assert "ade-engine @" not in pyproject


def test_import_archive_does_not_mutate_pyproject_dependencies(tmp_path: Path) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr("src/ade_config/__init__.py", "__all__ = []\n")

    storage.validate_path = lambda path: ([], "sha256:test")  # type: ignore[method-assign]
    storage.import_archive(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        archive=archive_bytes.getvalue(),
    )

    pyproject = storage.config_path(workspace_id, configuration_id) / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert "dependencies = [\"ade-engine\"]" in content
    assert "allow-direct-references" not in content


def test_import_archive_strips_single_wrapper_directory(tmp_path: Path) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "ade-config-main/pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr("ade-config-main/src/ade_config/__init__.py", "__all__ = []\n")

    storage.import_archive(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        archive=archive_bytes.getvalue(),
    )

    config_root = storage.config_path(workspace_id, configuration_id)
    assert (config_root / "pyproject.toml").is_file()
    assert (config_root / "src" / "ade_config" / "__init__.py").is_file()
    assert not (config_root / "ade-config-main").exists()


def test_import_archive_strips_nested_wrappers_for_large_non_source_file(tmp_path: Path) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    log_payload = b"a" * (600 * 1024)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "outer/inner/pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr("outer/inner/src/ade_config/__init__.py", "__all__ = []\n")
        zf.writestr("outer/inner/logs/engine_events.ndjson", log_payload)

    storage.import_archive(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        archive=archive_bytes.getvalue(),
    )

    config_root = storage.config_path(workspace_id, configuration_id)
    assert (config_root / "logs" / "engine_events.ndjson").read_bytes() == log_payload
    assert not (config_root / "outer").exists()


def test_import_archive_rejects_file_over_configured_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    monkeypatch.setattr(config_storage_module, "_IMPORT_DEFAULT_MAX_BYTES", 2048)

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "wrapped/pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr("wrapped/src/ade_config/__init__.py", "__all__ = []\n")
        zf.writestr("wrapped/logs/too_big.ndjson", b"x" * 4096)

    with pytest.raises(ConfigImportError) as exc_info:
        storage.import_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=archive_bytes.getvalue(),
        )

    assert exc_info.value.code == "file_too_large"
    assert exc_info.value.limit == 2048
    assert exc_info.value.detail == "logs/too_big.ndjson"


def test_replace_archive_rolls_back_on_final_swap_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    original_archive = _build_import_archive(init_content="ORIGINAL\n")
    replacement_archive = _build_import_archive(init_content="REPLACED\n")
    storage.import_archive(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        archive=original_archive,
    )

    destination = storage.config_path(workspace_id, configuration_id)
    original_replace = Path.replace

    def _replace_with_failure(self: Path, target: Path | str) -> Path:
        target_path = Path(target)
        if self.name.startswith(f".import-{configuration_id}") and target_path == destination:
            raise OSError("simulated_final_swap_failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _replace_with_failure)

    with pytest.raises(OSError, match="simulated_final_swap_failure"):
        storage.replace_from_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=replacement_archive,
        )

    init_file = destination / "src" / "ade_config" / "__init__.py"
    assert init_file.read_text(encoding="utf-8") == "ORIGINAL\n"

    workspace_root = storage.workspace_root(workspace_id)
    if workspace_root.exists():
        residual = [
            path.name
            for path in workspace_root.iterdir()
            if path.name.startswith(".import-") or path.name.startswith(".replace-backup-")
        ]
        assert residual == []


def test_import_archive_failure_cleans_temp_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()
    monkeypatch.setattr(config_storage_module, "_IMPORT_DEFAULT_MAX_BYTES", 2048)
    archive = _build_import_archive(
        wrapper="wrapped",
        extra_files={"logs/too_big.ndjson": b"x" * 4096},
    )

    with pytest.raises(ConfigImportError):
        storage.import_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=archive,
        )

    assert not storage.config_path(workspace_id, configuration_id).exists()
    workspace_root = storage.workspace_root(workspace_id)
    if workspace_root.exists():
        residual = [
            path.name
            for path in workspace_root.iterdir()
            if path.name.startswith(".import-") or path.name.startswith(".replace-backup-")
        ]
        assert residual == []


def test_import_archive_maps_runtime_zip_read_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    class BrokenZipFile:
        def __init__(self, *args, **kwargs) -> None:
            _ = args, kwargs

        def __enter__(self):
            raise RuntimeError("unsupported zip stream")

        def __exit__(self, exc_type, exc, tb) -> bool:
            _ = exc_type, exc, tb
            return False

    monkeypatch.setattr(config_storage_module.zipfile, "ZipFile", BrokenZipFile)

    with pytest.raises(ConfigImportError) as exc_info:
        storage.import_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=b"zip-bytes",
        )

    assert exc_info.value.code == "invalid_archive"
    assert exc_info.value.detail == "Archive could not be read"
