"""Job-centric streaming endpoints.

A "job" is the unit of work the UI cares about (build + engine run). Internally this
is implemented using the existing run orchestration, but the streaming contract is
UI-friendly and SSE-native:

- One stream per job run
- Standard SSE `event:` names
- High-volume log lines are plain text (no JSON parsing required on the client)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Security, status
from fastapi.responses import StreamingResponse

from ade_api.api.deps import get_runs_service
from ade_api.common.events import utc_rfc3339_now
from ade_api.common.sse import sse_json, sse_text
from ade_api.core.http import require_authenticated
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunsService

runs_service_dependency = Depends(get_runs_service)

router = APIRouter(
    tags=["jobs"],
    dependencies=[Security(require_authenticated)],
)


def _normalize_level(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"debug", "info", "warning", "error", "success"}:
            return lowered
        if lowered in {"warn"}:
            return "warning"
    return "info"


def _detect_scope(event_name: str, payload: dict[str, Any]) -> str:
    if event_name.startswith("build."):
        return "build"
    if event_name == "console.line":
        scope = payload.get("scope")
        if isinstance(scope, str) and scope.strip():
            return scope.strip().lower()
    return "run"


def _format_log_line(event: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return (scope, level, text) for an EventRecord, or None to skip."""

    event_name = str(event.get("event") or "").strip()
    payload = event.get("data") if isinstance(event.get("data"), dict) else {}
    payload = payload if isinstance(payload, dict) else {}

    scope = _detect_scope(event_name, payload)
    level = _normalize_level(payload.get("level") or event.get("level"))

    if event_name == "console.line":
        message = payload.get("message")
        text = message if isinstance(message, str) else str(event.get("message") or "")
    else:
        text = str(event.get("message") or "").strip() or event_name

    if not isinstance(text, str) or not text.strip():
        return None
    return scope, level, text


@router.get("/configurations/{configuration_id}/jobs/stream")
async def stream_configuration_job_endpoint(
    request: Request,
    configuration_id: UUID = Path(description="Configuration identifier"),
    options: RunCreateOptions = Depends(),
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
    """Create and execute a job while streaming output over SSE.

    Notes:
    - This endpoint is intentionally one-shot: it does not support replay/resume.
    - High-volume output (`console.line`) is streamed as plain text SSE events.
    """

    async def event_stream():
        out_id = 0

        run = await service.prepare_run(configuration_id=configuration_id, options=options)

        meta_details = {
            "jobId": str(run.id),
            "runId": str(run.id),
            "workspaceId": str(run.workspace_id),
            "configurationId": str(run.configuration_id),
            "buildId": str(run.build_id) if run.build_id else None,
        }
        meta = {
            "id": out_id,
            "ts": utc_rfc3339_now(),
            "scope": "meta",
            "level": "info",
            "text": "connected",
            "details": meta_details,
        }
        yield sse_json("meta", meta, event_id=out_id)

        async for frame in service.stream_run(run_id=run.id, options=options):
            if await request.is_disconnected():
                break
            if not isinstance(frame, dict):
                continue

            out_id += 1
            ts = str(frame.get("timestamp") or utc_rfc3339_now())
            formatted = _format_log_line(frame)
            if formatted is None:
                continue
            scope, level, text = formatted

            yield sse_text("log", f"{scope}\t{level}\t{ts}\t{text}", event_id=out_id)

            if frame.get("event") == "run.complete":
                out_id += 1
                details = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                status_value = str(details.get("status") or "").lower()
                done_level = (
                    "success"
                    if status_value in {"succeeded", "success"}
                    else "warning"
                    if status_value in {"cancelled", "canceled"}
                    else "error"
                )
                done = {
                    "id": out_id,
                    "ts": utc_rfc3339_now(),
                    "scope": "run",
                    "level": done_level,
                    "text": f"completed ({status_value or 'unknown'})",
                    "details": details,
                }
                yield sse_json("done", done, event_id=out_id)
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        status_code=status.HTTP_200_OK,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{job_id}/events/stream")
async def stream_job_events_endpoint(
    request: Request,
    job_id: UUID = Path(description="Job identifier (run id)"),
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
    """Tail a running job's events as SSE (live only, no replay/resume)."""

    run = await service.get_run(job_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")

    async def event_stream():
        out_id = 0
        meta_details = {
            "jobId": str(run.id),
            "runId": str(run.id),
            "workspaceId": str(run.workspace_id),
            "configurationId": str(run.configuration_id),
            "buildId": str(getattr(run, "build_id", None)) if getattr(run, "build_id", None) else None,
        }
        meta = {
            "id": out_id,
            "ts": utc_rfc3339_now(),
            "scope": "meta",
            "level": "info",
            "text": "connected",
            "details": meta_details,
        }
        yield sse_json("meta", meta, event_id=out_id)

        async with service.subscribe_to_events(run) as subscription:
            async for event in subscription:
                if await request.is_disconnected():
                    break
                if not isinstance(event, dict):
                    continue
                out_id += 1
                ts = str(event.get("timestamp") or utc_rfc3339_now())
                formatted = _format_log_line(event)
                if formatted is None:
                    continue
                scope, level, text = formatted
                yield sse_text("log", f"{scope}\t{level}\t{ts}\t{text}", event_id=out_id)
                if event.get("event") == "run.complete":
                    out_id += 1
                    details = event.get("data") if isinstance(event.get("data"), dict) else {}
                    status_value = str(details.get("status") or "").lower()
                    done_level = (
                        "success"
                        if status_value in {"succeeded", "success"}
                        else "warning"
                        if status_value in {"cancelled", "canceled"}
                        else "error"
                    )
                    done = {
                        "id": out_id,
                        "ts": utc_rfc3339_now(),
                        "scope": "run",
                        "level": done_level,
                        "text": f"completed ({status_value or 'unknown'})",
                        "details": details,
                    }
                    yield sse_json("done", done, event_id=out_id)
                    break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        status_code=status.HTTP_200_OK,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
