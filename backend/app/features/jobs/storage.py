"""Filesystem helpers for job execution artifacts."""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from backend.app.shared.core.config import Settings
from .types import ResolvedInput

_SAFE_FILENAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


@dataclass(slots=True)
class JobStoragePaths:
    job_dir: Path
    config_dir: Path
    inputs_dir: Path
    artifact_path: Path
    output_path: Path
    logs_path: Path
    request_path: Path


class JobsStorage:
    """Manage on-disk storage for job runs."""

    def __init__(self, settings: Settings) -> None:
        self._base_dir = Path(settings.storage_data_dir) / "jobs"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, job_id: str) -> JobStoragePaths:
        job_dir = self._base_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        config_dir = job_dir / "config"
        inputs_dir = job_dir / "inputs"
        artifact_path = job_dir / "artifact.json"
        output_path = job_dir / "normalized.xlsx"
        logs_path = job_dir / "events.ndjson"
        request_path = job_dir / "run-request.json"
        config_dir.mkdir(parents=True, exist_ok=True)
        inputs_dir.mkdir(parents=True, exist_ok=True)
        logs_path.touch(exist_ok=True)
        request_path.touch(exist_ok=True)
        return JobStoragePaths(
            job_dir=job_dir,
            config_dir=config_dir,
            inputs_dir=inputs_dir,
            artifact_path=artifact_path,
            output_path=output_path,
            logs_path=logs_path,
            request_path=request_path,
        )

    def copy_config(self, source: Path, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    def write_run_request(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def append_log(self, path: Path, event: dict[str, Any]) -> None:
        enriched = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(enriched, separators=(",", ":")) + "\n")

    def stage_inputs(self, inputs_dir: Path, inputs: Iterable[ResolvedInput]) -> list[Path]:
        staged: list[Path] = []
        for index, descriptor in enumerate(inputs, start=1):
            candidate = self._safe_filename(descriptor.filename, fallback=descriptor.document_id, index=index)
            destination = inputs_dir / candidate
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(descriptor.source_path, destination)
            staged.append(destination)
        return staged

    def cleanup_inputs(self, paths: JobStoragePaths) -> None:
        if paths.inputs_dir.exists():
            shutil.rmtree(paths.inputs_dir, ignore_errors=True)

    @staticmethod
    def _safe_filename(name: str, *, fallback: str, index: int) -> str:
        base = Path(name or fallback or f"input-{index}").name or f"input-{index}"
        cleaned = []
        for char in base:
            cleaned.append(char if char in _SAFE_FILENAME_CHARS else "_")
        sanitized = "".join(cleaned).strip("._") or f"input-{index}"
        return f"{index:02d}_{sanitized}"


__all__ = ["JobsStorage", "JobStoragePaths"]
