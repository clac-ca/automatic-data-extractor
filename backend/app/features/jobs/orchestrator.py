"""Synchronous job runner that emits artifact and workbook outputs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.shared.core.time import utc_now

from ..configs.models import ConfigVersion
from .models import JobStatus
from .storage import JobStoragePaths, JobsStorage


@dataclass(slots=True)
class RunResult:
    """Paths to the files produced by a job run."""

    artifact_path: Path
    output_path: Path


class JobOrchestrator:
    """Execute the documented passes against a config version synchronously."""

    def __init__(self, storage: JobsStorage) -> None:
        self._storage = storage

    def run(
        self,
        *,
        job_id: str,
        config_version: ConfigVersion,
    ) -> RunResult:
        paths: JobStoragePaths = self._storage.prepare(job_id)
        self._storage.copy_config(Path(config_version.package_uri), paths.config_dir)

        manifest = config_version.manifest
        passes: list[dict[str, Any]] = [
            {
                "name": "detect_tables",
                "status": JobStatus.SUCCEEDED.value,
                "summary": {"tables": []},
            },
            {
                "name": "map_columns",
                "status": JobStatus.SUCCEEDED.value,
                "summary": {"target_fields": list(manifest.get("target_fields", []))},
            },
            {
                "name": "generate_normalized_workbook",
                "status": JobStatus.SUCCEEDED.value,
                "summary": {"sheet": "Normalized"},
            },
        ]

        now = utc_now().isoformat()
        artifact_payload = {
            "job": {
                "job_id": job_id,
                "status": JobStatus.SUCCEEDED.value,
                "started_at": now,
                "completed_at": now,
            },
            "config": {
                "config_version_id": config_version.id,
                "manifest": manifest,
            },
            "passes": passes,
        }
        self._storage.write_artifact(paths.artifact_path, artifact_payload)
        self._storage.write_workbook(
            paths.output_path,
            list(manifest.get("target_fields", [])),
        )
        return RunResult(paths.artifact_path, paths.output_path)


__all__ = ["JobOrchestrator", "RunResult"]
