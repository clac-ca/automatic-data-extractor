"""Sandboxed job runner executed as a subprocess."""

from __future__ import annotations

import json
import os
import resource
import socket
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from openpyxl import Workbook
except ModuleNotFoundError as exc:  # pragma: no cover - dependency should exist
    raise SystemExit(f"openpyxl is required for job execution: {exc}")

from backend.app.features.jobs.runtime import PipelineRunner


def main() -> None:
    try:
        request = _read_request()
        disable_network(allow=os.environ.get("ADE_ALLOW_NETWORK") == "1")
        apply_resource_limits()
        result = run_job(request)
    except Exception as exc:  # pragma: no cover - defensive path
        diagnostics = [
            {
                "level": "error",
                "code": "exception",
                "message": f"Unhandled error: {exc}",
            }
        ]
        result = {
            "schema": "ade.run_result/v1",
            "status": "failed",
            "diagnostics": diagnostics,
            "error_message": str(exc),
        }
        traceback.print_exc()
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw:
        raise ValueError("Empty run request")
    payload = json.loads(raw)
    if payload.get("schema") != "ade.run_request/v1":
        raise ValueError("Unsupported run request schema")
    return payload


def apply_resource_limits() -> None:
    cpu_seconds = int(os.environ.get("ADE_WORKER_CPU_SECONDS", "60"))
    mem_limit = int(os.environ.get("ADE_WORKER_MEM_MB", "512")) * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except Exception:  # pragma: no cover - may not be supported
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    except Exception:  # pragma: no cover
        pass


def disable_network(*, allow: bool) -> None:
    if allow:
        return

    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise ConnectionError("Networking is disabled for this job")

    socket.socket = lambda *a, **k: (_blocked(*a, **k))  # type: ignore[assignment]
    socket.create_connection = lambda *a, **k: (_blocked(*a, **k))  # type: ignore[assignment]


def run_job(request: dict[str, Any]) -> dict[str, Any]:
    manifest_path = Path(request["manifest_path"]).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    input_paths = [str(path) for path in request.get("input_paths", [])]

    job_context = {
        "job_id": request.get("job_id"),
        "config_version_id": request.get("config_version_id"),
        "trace_id": os.environ.get("ADE_TRACE_ID"),
        "input_paths": input_paths,
    }

    pipeline = PipelineRunner(
        config_dir=manifest_path.parent,
        manifest=manifest,
        job_context=job_context,
        input_paths=input_paths,
    )
    pipeline_result = pipeline.execute()

    sheet_title = pipeline_result.sheet_title

    work_dir = Path(request["work_dir"]) if request.get("work_dir") else manifest_path.parent
    artifact_path = Path(os.environ.get("ADE_ARTIFACT_PATH", work_dir / "artifact.json"))
    output_path = Path(os.environ.get("ADE_OUTPUT_PATH", work_dir / "normalized.xlsx"))

    started_at = datetime.now(timezone.utc)

    passes = list(pipeline_result.pass_summaries)

    columns_section = manifest.get("columns", {}) if isinstance(manifest, dict) else {}
    manifest_order = list(columns_section.get("order", []) or [])
    manifest_meta = columns_section.get("meta", {}) or {}
    enabled_fields = [field for field in manifest_order if manifest_meta.get(field, {}).get("enabled", True)]
    header_labels = [str(manifest_meta.get(field, {}).get("label") or field) for field in enabled_fields]

    field_assignments = {
        assignment.target_field: assignment
        for assignment in pipeline_result.assignments
        if assignment.target_field
    }

    row_count = 0
    for assignment in field_assignments.values():
        row_count = max(row_count, len(assignment.transformed_values))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.delete_rows(1, sheet.max_row)
    sheet.append(header_labels)

    for row_index in range(row_count):
        output_row: list[Any] = []
        for field in enabled_fields:
            assignment = field_assignments.get(field)
            value = None
            if assignment and row_index < len(assignment.transformed_values):
                value = assignment.transformed_values[row_index]
            output_row.append(value)
        sheet.append(output_row)

    workbook.save(output_path)

    generate_summary = {
        "name": "generate_normalized_workbook",
        "status": "succeeded",
        "summary": {
            "sheet": sheet_title,
            "headers": header_labels,
            "row_count": row_count,
        },
    }
    passes.append(generate_summary)

    artifact = deepcopy(pipeline_result.artifact_template)
    artifact.update(
        {
            "schema": "ade.artifact/v1",
            "job": {
                "job_id": request.get("job_id"),
                "trace_id": os.environ.get("ADE_TRACE_ID"),
                "status": "succeeded",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            "config": {
                "config_version_id": request.get("config_version_id"),
            },
            "passes": passes,
        }
    )

    pipeline.run_job_end(artifact)

    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    return {
        "schema": "ade.run_result/v1",
        "status": "succeeded",
        "artifact_path": str(artifact_path),
        "output_path": str(output_path),
        "diagnostics": pipeline_result.diagnostics,
    }

if __name__ == "__main__":
    main()
