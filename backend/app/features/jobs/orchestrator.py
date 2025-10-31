"""Subprocess-backed job orchestrator."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from backend.app.features.configs.spec import ManifestV1

from ..configs.models import ConfigVersion
from .storage import JobStoragePaths, JobsStorage
from .types import ResolvedInput

WORKER_SCRIPT = Path(__file__).with_name("worker.py")


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

    def __init__(self, storage: JobsStorage) -> None:
        self._storage = storage

    async def run(
        self,
        *,
        job_id: str,
        config_version: ConfigVersion,
        manifest: ManifestV1,
        trace_id: str,
        input_files: Sequence[ResolvedInput],
        timeout_seconds: float,
    ) -> tuple[RunResult, JobStoragePaths]:
        paths: JobStoragePaths = self._storage.prepare(job_id)
        self._storage.copy_config(Path(config_version.package_path), paths.config_dir)
        staged_inputs = self._storage.stage_inputs(paths.inputs_dir, input_files)
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
        }
        self._storage.write_run_request(paths.request_path, request_payload)

        env = self._build_env(paths=paths, manifest=manifest, trace_id=trace_id)
        request_bytes = json.dumps(request_payload, separators=(",", ":")).encode("utf-8")

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-B",
            str(WORKER_SCRIPT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(paths.job_dir),
            env=env,
        )
        self._storage.append_log(
            paths.logs_path,
            {
                "event": "worker.spawn",
                "trace_id": trace_id,
                "pid": process.pid,
                "timeout_seconds": timeout_seconds,
            },
        )

        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(request_bytes), timeout_seconds)
        except asyncio.TimeoutError:
            timed_out = True
            self._storage.append_log(
                paths.logs_path,
                {"event": "worker.timeout", "trace_id": trace_id},
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
            self._storage.append_log(
                paths.logs_path,
                {
                    "event": "worker.stderr",
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
            status = "failed"
            artifact_path = None
            output_path = None

        self._storage.append_log(
            paths.logs_path,
            {
                "event": "worker.exit",
                "trace_id": trace_id,
                "exit_code": exit_code,
                "elapsed_ms": elapsed_ms,
                "timed_out": timed_out,
                "status": status,
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

    def _build_env(
        self,
        *,
        paths: JobStoragePaths,
        manifest: ManifestV1,
        trace_id: str,
    ) -> dict[str, str]:
        default_cpu_seconds = max(1, manifest.engine.defaults.timeout_ms // 1000)
        cpu_override = os.environ.get("ADE_WORKER_CPU_SECONDS")
        mem_override = os.environ.get("ADE_WORKER_MEM_MB")

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": os.pathsep.join(
                filter(
                    None,
                    [
                        str((paths.config_dir / "vendor").resolve()),
                        str(paths.config_dir.resolve()),
                    ],
                )
            ),
            "ADE_CONFIG_DIR": str(paths.config_dir),
            "ADE_ARTIFACT_PATH": str(paths.artifact_path),
            "ADE_OUTPUT_PATH": str(paths.output_path),
            "ADE_WORK_DIR": str(paths.job_dir),
            "ADE_TRACE_ID": trace_id,
            "ADE_ALLOW_NETWORK": "1" if manifest.engine.defaults.allow_net else "0",
            "ADE_WORKER_CPU_SECONDS": str(int(cpu_override) if cpu_override else default_cpu_seconds),
            "ADE_WORKER_MEM_MB": str(int(mem_override) if mem_override else manifest.engine.defaults.memory_mb),
        }

        for key, value in manifest.env.items():
            if key:
                env[str(key)] = str(value)

        return env


__all__ = ["JobOrchestrator", "RunResult"]
