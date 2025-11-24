import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from ade_engine.config.hook_registry import HookStage
from ade_engine.config.loader import load_config_runtime
from ade_engine.core.errors import HookError
from ade_engine.core.hooks import run_hooks
from ade_engine.core.types import RawTable, RunContext, RunPaths, RunResult, RunStatus
from ade_engine.infra.artifact import FileArtifactSink
from ade_engine.infra.telemetry import PipelineLogger


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


def _run_context(runtime, tmp_path: Path) -> tuple[RunContext, FileArtifactSink, PipelineLogger]:
    paths = RunPaths(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "artifact.json",
        events_path=tmp_path / "events.ndjson",
    )
    paths.input_dir.mkdir()
    paths.output_dir.mkdir()
    paths.logs_dir.mkdir()

    run = RunContext(
        run_id="run-123",
        metadata={},
        manifest=runtime.manifest,
        paths=paths,
        started_at=datetime.utcnow(),
    )
    artifact_sink = FileArtifactSink(artifact_path=paths.artifact_path)
    artifact_sink.start(run, runtime.manifest)
    logger = PipelineLogger(run=run, artifact_sink=artifact_sink)
    return run, artifact_sink, logger


def test_hooks_execute_in_order_and_allow_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)

    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "name": "Hook Config",
        "description": None,
        "script_api_version": 1,
        "columns": {"order": [], "fields": {}},
        "hooks": {
            "on_run_start": [],
            "on_after_extract": ["hooks.first", "hooks.second"],
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

    hooks_dir = pkg_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("")
    (hooks_dir / "first.py").write_text(
        """
def run(context):
    context.state.setdefault("order", []).append("first")
    context.logger.note("first note", stage=context.stage.value)
"""
    )
    (hooks_dir / "second.py").write_text(
        """
def run(*, tables, run, logger, **_):
    run.state.setdefault("order", []).append("second")
    tables[0].header_row.append("extra")
    logger.note("second note", stage="kw")
"""
    )

    runtime = load_config_runtime(package="ade_config", manifest_path=manifest_path)
    run, artifact_sink, logger = _run_context(runtime, tmp_path)

    tables = [
        RawTable(
            source_file=run.paths.input_dir / "sample.csv",
            source_sheet=None,
            table_index=1,
            header_row=["col1"],
            data_rows=[["a"], ["b"]],
            header_row_index=1,
            first_data_row_index=2,
            last_data_row_index=3,
        )
    ]

    run_hooks(
        stage=HookStage.ON_AFTER_EXTRACT,
        registry=runtime.hooks,
        run=run,
        manifest=runtime.manifest,
        artifact=artifact_sink,
        logger=logger,
        tables=tables,
    )

    assert run.state["order"] == ["first", "second"]
    assert tables[0].header_row == ["col1", "extra"]
    assert len(artifact_sink._artifact.notes) == 2


def test_hook_failure_raises_hookerror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)

    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "name": "Hook Config",
        "description": None,
        "script_api_version": 1,
        "columns": {"order": [], "fields": {}},
        "hooks": {
            "on_run_start": [],
            "on_after_extract": [],
            "on_after_mapping": [],
            "on_before_save": [],
            "on_run_end": ["hooks.fail"],
        },
        "writer": {
            "append_unmapped_columns": True,
            "unmapped_prefix": "raw_",
            "output_sheet": "Normalized",
        },
        "extra": None,
    }
    manifest_path = _write_manifest(pkg_dir, manifest)

    hooks_dir = pkg_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("")
    (hooks_dir / "fail.py").write_text(
        """
def run(context):
    raise RuntimeError("boom")
"""
    )

    runtime = load_config_runtime(package="ade_config", manifest_path=manifest_path)
    run, artifact_sink, logger = _run_context(runtime, tmp_path)

    result = RunResult(
        status=RunStatus.SUCCEEDED,
        error=None,
        run_id=run.run_id,
        output_paths=(),
        artifact_path=run.paths.artifact_path,
        events_path=run.paths.events_path,
        processed_files=(),
    )

    with pytest.raises(HookError) as excinfo:
        run_hooks(
            stage=HookStage.ON_RUN_END,
            registry=runtime.hooks,
            run=run,
            manifest=runtime.manifest,
            artifact=artifact_sink,
            logger=logger,
            result=result,
        )

    assert "on_run_end" in str(excinfo.value)
