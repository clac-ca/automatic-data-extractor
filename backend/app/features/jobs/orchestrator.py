"""Subprocess-backed job orchestrator."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from backend.app.features.configs.activation_env import (
    ActivationMetadata,
    ActivationMetadataStore,
)
from backend.app.features.configs.spec import ManifestV1
from backend.app.shared.core.config import Settings

from ..configs.models import ConfigVersion
from .models import JobStatus
from .storage import JobStoragePaths, JobsStorage
from .types import ResolvedInput

WORKER_SCRIPT = Path(__file__).with_name("worker.py")
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunResult:
    """Result returned from the worker subprocess."""

    status: str
    artifact_path: Path | None
    output_path: Path | None
    diagnostics: list[dict[str, Any]]
    error_message: str | None
    timed_out: bool
    exit_code: int
    elapsed_ms: int


class JobOrchestrator:
    """Launch jobs in an isolated Python subprocess using a JSON protocol."""

    def __init__(
        self,
        storage: JobsStorage,
        *,
        settings: Settings,
        safe_mode_message: str,
        activation_store: ActivationMetadataStore,
    ) -> None:
        self._storage = storage
        self._settings = settings
        self._safe_mode_message = safe_mode_message
        self._activation_store = activation_store

    async def run(
        self,
        *,
        job_id: str,
        attempt: int,
        config_version: ConfigVersion,
        manifest: ManifestV1,
        trace_id: str,
        input_files: Sequence[ResolvedInput],
        timeout_seconds: float,
        paths: JobStoragePaths | None = None,
    ) -> tuple[RunResult, JobStoragePaths]:
        if self._settings.safe_mode:
            logger.warning(
                "Job orchestrator invoked while ADE_SAFE_MODE is enabled; aborting execution.",
                extra={
                    "job_id": job_id,
                    "config_version_id": config_version.id,
                    "trace_id": trace_id,
                },
            )
            raise RuntimeError(self._safe_mode_message)

        owns_paths = paths is None
        paths = paths or self._storage.prepare(job_id)
        self._storage.copy_config(Path(config_version.package_path), paths.config_dir)
        staged_inputs = self._storage.stage_inputs(paths.inputs_dir, input_files)
        activation = self._activation_store.load(config_id=config_version.config_id, version=config_version)
        python_executable = (
            activation.python_executable
            if activation and activation.ready and activation.python_executable is not None
            else Path(sys.executable)
        )

        request_payload = {
            "schema": "ade.run_request/v1",
            "job_id": job_id,
            "config_version_id": config_version.id,
            "manifest_path": str(paths.config_dir / "manifest.json"),
            "input_paths": [str(path) for path in staged_inputs],
            "input_documents": [
                {
                    "document_id": descriptor.document_id,
                    "filename": descriptor.filename,
                    "sha256": descriptor.sha256,
                    "path": str(path),
                }
                for descriptor, path in zip(input_files, staged_inputs)
            ],
            "work_dir": str(paths.job_dir),
            "python_executable": str(python_executable),
        }
        self._storage.write_run_request(paths.request_path, request_payload)

        env = self._build_env(
            paths=paths,
            manifest=manifest,
            trace_id=trace_id,
            activation=activation,
        )
        request_bytes = json.dumps(request_payload, separators=(",", ":")).encode("utf-8")

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            str(python_executable),
            "-I",
            "-B",
            str(WORKER_SCRIPT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(paths.job_dir),
            env=env,
        )
        timed_out = False
        try:
            self._storage.record_event(
                paths.logs_path,
                event="worker.spawn",
                job_id=job_id,
                attempt=attempt,
                state=JobStatus.RUNNING.value,
                detail={
                    "trace_id": trace_id,
                    "pid": process.pid,
                    "timeout_seconds": timeout_seconds,
                },
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(request_bytes), timeout_seconds)
            except asyncio.TimeoutError:
                timed_out = True
                self._storage.record_event(
                    paths.logs_path,
                    event="worker.timeout",
                    job_id=job_id,
                    attempt=attempt,
                    state=JobStatus.RUNNING.value,
                    detail={"trace_id": trace_id},
                )
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                stdout, stderr = b"", b""

            elapsed_ms = int((time.monotonic() - start) * 1000)
            exit_code = process.returncode if process.returncode is not None else -1

            if stderr:
                self._storage.record_event(
                    paths.logs_path,
                    event="worker.stderr",
                    job_id=job_id,
                    attempt=attempt,
                    state=JobStatus.RUNNING.value,
                    detail={
                        "trace_id": trace_id,
                        "payload": stderr.decode("utf-8", errors="replace")[:4000],
                    },
                )

            result_payload: dict[str, Any] | None = None
            error_message: str | None = None
            diagnostics: list[dict[str, Any]] = []

            if stdout:
                try:
                    result_payload = json.loads(stdout.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    error_message = f"Worker produced invalid JSON: {exc}"
            elif not timed_out:
                error_message = "Worker produced no output"

            if result_payload is not None:
                diagnostics = list(result_payload.get("diagnostics", []))
                error_message = result_payload.get("error_message") or error_message
                status = str(result_payload.get("status", "failed"))
                artifact_path = result_payload.get("artifact_path")
                output_path = result_payload.get("output_path")
            else:
                status = JobStatus.FAILED.value
                artifact_path = None
                output_path = None

            self._storage.record_event(
                paths.logs_path,
                event="worker.exit",
                job_id=job_id,
                attempt=attempt,
                state=status,
                duration_ms=elapsed_ms,
                detail={
                    "trace_id": trace_id,
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                },
            )

            run_result = RunResult(
                status=status,
                artifact_path=Path(artifact_path).resolve() if artifact_path else None,
                output_path=Path(output_path).resolve() if output_path else None,
                diagnostics=diagnostics,
                error_message=error_message,
                timed_out=timed_out,
                exit_code=exit_code,
                elapsed_ms=elapsed_ms,
            )
            return run_result, paths
        finally:
            if owns_paths:
                self._storage.cleanup_inputs(paths)

    def _build_env(
        self,
        *,
        paths: JobStoragePaths,
        manifest: ManifestV1,
        trace_id: str,
        activation: ActivationMetadata | None,
    ) -> dict[str, str]:
        default_cpu_seconds = max(1, manifest.engine.defaults.timeout_ms // 1000)
        cpu_override = os.environ.get("ADE_WORKER_CPU_SECONDS")
        mem_override = os.environ.get("ADE_WORKER_MEM_MB")

        pythonpath_parts = [str(paths.config_dir.resolve())]
        vendor_dir = (paths.config_dir / "vendor").resolve()
        if not activation or not activation.ready:
            pythonpath_parts.insert(0, str(vendor_dir))

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": os.pathsep.join(filter(None, pythonpath_parts)),
            "ADE_CONFIG_DIR": str(paths.config_dir),
            "ADE_ARTIFACT_PATH": str(paths.artifact_path),
            "ADE_OUTPUT_PATH": str(paths.output_path),
            "ADE_WORK_DIR": str(paths.job_dir),
            "ADE_TRACE_ID": trace_id,
            "ADE_RUNTIME_NETWORK_ACCESS": "1"
            if manifest.engine.defaults.runtime_network_access
            else "0",
            "ADE_WORKER_CPU_SECONDS": str(int(cpu_override) if cpu_override else default_cpu_seconds),
            "ADE_WORKER_MEM_MB": str(int(mem_override) if mem_override else manifest.engine.defaults.memory_mb),
        }

        for key, value in manifest.env.items():
            if key:
                env[str(key)] = str(value)

        return env


__all__ = ["JobOrchestrator", "RunResult"]
