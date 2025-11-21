from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext, JobPaths
from ade_engine.hooks import HookContext, HookExecutionError, HookRegistry, HookStage
from ade_engine.telemetry.sinks import ArtifactSink


@dataclass
class DummyArtifact(ArtifactSink):
    notes: list[dict[str, Any]] | None = None

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None: ...

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None:
        self.notes = self.notes or []
        self.notes.append({"message": message, "level": level, "extra": extra})

    def record_table(self, table: dict[str, Any]) -> None: ...

    def mark_success(self, *, completed_at, outputs) -> None: ...

    def mark_failure(self, *, completed_at, error) -> None: ...

    def flush(self) -> None: ...


def _job() -> JobContext:
    paths = JobPaths(
        jobs_root=Path("/tmp"),
        job_dir=Path("/tmp"),
        input_dir=Path("/tmp"),
        output_dir=Path("/tmp"),
        logs_dir=Path("/tmp"),
        artifact_path=Path("/tmp/artifact.json"),
        events_path=Path("/tmp/events.ndjson"),
    )
    return JobContext(
        job_id="job",
        manifest={},
        paths=paths,
        started_at=datetime.utcnow(),
    )


def _install_temp_hook(tmp_path: Path) -> str:
    pkg = tmp_path / "test_hooks_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    hooks_dir = pkg / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("", encoding="utf-8")
    (hooks_dir / "on_job_start.py").write_text(
        "def run(job=None, artifact=None, **_: object):\n"
        "    artifact.note('hello', level='info')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    return "test_hooks_pkg"


def test_hook_registry_executes_and_passes_context(tmp_path: Path):
    package = _install_temp_hook(tmp_path)
    manifest = ManifestContext(
        raw={
            "hooks": {
                "on_job_start": [{"script": "hooks/on_job_start.py"}],
            }
        },
        model=None,
    )
    registry = HookRegistry(manifest, package=package)

    artifact = DummyArtifact()
    ctx = HookContext(job=_job(), artifact=artifact)

    registry.call(HookStage.ON_JOB_START, ctx)

    assert artifact.notes and artifact.notes[0]["message"] == "hello"


def test_hook_registry_raises_on_failure(tmp_path: Path):
    package = _install_temp_hook(tmp_path)
    manifest = ManifestContext(
        raw={
            "hooks": {
                "on_job_start": [{"script": "hooks/on_job_start.py"}],
            }
        },
        model=None,
    )
    registry = HookRegistry(manifest, package=package)
    artifact = DummyArtifact()
    ctx = HookContext(job=_job(), artifact=artifact)

    # Monkeypatch the module to throw
    mod = importlib.import_module(f"{package}.hooks.on_job_start")
    mod.run = lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))

    try:
        registry.call(HookStage.ON_JOB_START, ctx)
    except HookExecutionError as exc:
        assert "boom" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("HookExecutionError not raised")
