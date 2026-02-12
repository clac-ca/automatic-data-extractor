from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path

import ade_worker.gc as gc_module
from ade_worker.gc import GcResult, run_gc


@dataclass
class _DummySettings:
    workspaces_dir: Path
    configs_dir: Path
    documents_dir: Path
    runs_dir: Path
    venvs_dir: Path
    pip_cache_dir: Path
    worker_runs_dir: Path
    worker_venvs_dir: Path
    worker_uv_cache_dir: Path
    worker_cache_ttl_days: int
    worker_run_artifact_ttl_days: int | None


class _DummyEngine:
    def dispose(self) -> None:
        return None


def test_run_gc_uses_timezone_aware_utc_now(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    settings = _DummySettings(
        workspaces_dir=data_root / "workspaces",
        configs_dir=data_root / "workspaces",
        documents_dir=data_root / "workspaces",
        runs_dir=tmp_path / "runs",
        venvs_dir=tmp_path / "venvs",
        pip_cache_dir=tmp_path / "cache" / "pip",
        worker_runs_dir=tmp_path / "runs",
        worker_venvs_dir=tmp_path / "venvs",
        worker_uv_cache_dir=tmp_path / "cache" / "uv",
        worker_cache_ttl_days=30,
        worker_run_artifact_ttl_days=30,
    )

    observed: dict[str, object] = {}

    def _fake_gc_local(*, paths, now, cache_ttl_days):  # noqa: ANN001
        observed["local_now"] = now
        return GcResult()

    def _fake_gc_runs(*, session_factory, paths, now, run_ttl_days):  # noqa: ANN001
        observed["run_now"] = now
        return GcResult()

    monkeypatch.setattr(gc_module, "build_engine", lambda _: _DummyEngine())
    monkeypatch.setattr(gc_module, "sessionmaker", lambda **_: object())
    monkeypatch.setattr(gc_module, "gc_local_venv_cache", _fake_gc_local)
    monkeypatch.setattr(gc_module, "gc_run_artifacts", _fake_gc_runs)

    run_gc(settings)

    local_now = observed.get("local_now")
    run_now = observed.get("run_now")
    assert local_now is not None
    assert run_now is not None
    assert getattr(local_now, "tzinfo", None) is timezone.utc
    assert getattr(run_now, "tzinfo", None) is timezone.utc
