"""Job-centric streaming endpoints.

A "job" is the unit of work the UI cares about (build + engine run). Internally this
is implemented using the existing run orchestration.

Streaming contract:
- Standard Server-Sent Events (SSE)
- Each event is emitted with `event: <event_name>` (e.g. `engine.detector.column_result`)
- Each event's `data:` is the JSON EventRecord emitted by the engine/API
- SSE `id:` uses the run stream sequence number (monotonic within the run)

This preserves the engine's rich structured payloads while still using a standard
SSE event dispatch model.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Security, status
from fastapi.responses import StreamingResponse

from ade_api.api.deps import get_runs_service
from ade_api.common.events import new_event_record
from ade_api.common.sse import sse_json
from ade_api.core.http import require_authenticated
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunsService

runs_service_dependency = Depends(get_runs_service)

router = APIRouter(
    tags=["jobs"],
    dependencies=[Security(require_authenticated)],
)


def _as_event_name(event: dict[str, Any]) -> str:
    name = event.get("event")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "message"


def _as_sse_id(event: dict[str, Any], fallback: int) -> int:
    value = event.get("sequence")
    if isinstance(value, int) and value >= 0:
        return value
    return fallback


@router.get("/configurations/{configuration_id}/jobs/stream")
async def stream_configuration_job_endpoint(
    request: Request,
    configuration_id: UUID = Path(description="Configuration identifier"),
    options: RunCreateOptions = Depends(),
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
    """Create and execute a job while streaming EventRecords over SSE (live only)."""

    async def event_stream():
        fallback_id = 0
        run = await service.prepare_run(configuration_id=configuration_id, options=options)

        meta = new_event_record(
            event="job.meta",
            level="info",
            message="connected",
            data={
                "jobId": str(run.id),
                "runId": str(run.id),
                "workspaceId": str(run.workspace_id),
                "configurationId": str(run.configuration_id),
                "buildId": str(run.build_id) if run.build_id else None,
            },
        )
        yield sse_json("job.meta", meta, event_id=0)

        async for frame in service.stream_run(run_id=run.id, options=options):
            if await request.is_disconnected():
                break
            if not isinstance(frame, dict):
                continue

            fallback_id += 1
            sse_id = _as_sse_id(frame, fallback_id)
            event_name = _as_event_name(frame)
            yield sse_json(event_name, frame, event_id=sse_id)
            if event_name == "run.complete":
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
    """Tail a job's events as SSE (live only, no replay/resume)."""

    run = await service.get_run(job_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")

    async def event_stream():
        fallback_id = 0
        meta = new_event_record(
            event="job.meta",
            level="info",
            message="connected",
            data={
                "jobId": str(run.id),
                "runId": str(run.id),
                "workspaceId": str(run.workspace_id),
                "configurationId": str(run.configuration_id),
                "buildId": str(getattr(run, "build_id", None)) if getattr(run, "build_id", None) else None,
            },
        )
        yield sse_json("job.meta", meta, event_id=0)

        async with service.subscribe_to_events(run) as subscription:
            async for event in subscription:
                if await request.is_disconnected():
                    break
                if not isinstance(event, dict):
                    continue
                fallback_id += 1
                sse_id = _as_sse_id(event, fallback_id)
                event_name = _as_event_name(event)
                yield sse_json(event_name, event, event_id=sse_id)
                if event_name == "run.complete":
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
