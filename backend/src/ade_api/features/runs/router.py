"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import unicodedata
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path as FilePath
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from ade_api.api.deps import SettingsDep, get_runs_service, get_runs_service_read
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.common.downloads import build_content_disposition
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookSheetPreview,
)
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.db import get_session_factory
from ade_api.features.configs.exceptions import (
    ConfigEngineDependencyMissingError,
    ConfigStateError,
    ConfigStorageNotFoundError,
    ConfigurationNotFoundError,
)
from ade_db.models import Run, RunStatus, User
from ade_storage import StorageLimitError, get_storage_adapter

from .exceptions import (
    RunDocumentMissingError,
    RunInputDocumentRequiredForProcessError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotCancellableError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunOutputPreviewParseError,
    RunOutputPreviewSheetNotFoundError,
    RunOutputPreviewUnsupportedError,
    RunOutputSheetParseError,
    RunOutputSheetUnsupportedError,
    RunSafeModeEnabledError,
)
from .filters import RunColumnFilters
from .schemas import (
    RunBatchCreateResponse,
    RunColumnResource,
    RunFieldResource,
    RunInput,
    RunMetricsResource,
    RunOutput,
    RunOutputSheet,
    RunPage,
    RunResource,
    RunWorkspaceBatchCreateRequest,
    RunWorkspaceCreateRequest,
)
from .service import RunsService
from .sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(
    prefix="/workspaces/{workspaceId}/runs",
    tags=["runs"],
    dependencies=[Security(require_authenticated)],
)
RunsServiceDep = Annotated[RunsService, Depends(get_runs_service)]
RunsServiceReadDep = Annotated[RunsService, Depends(get_runs_service_read)]

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
RunPath = Annotated[
    UUID,
    Path(
        description="Run identifier",
        alias="runId",
    ),
]
RunReader = Annotated[
    User,
    Security(
        require_workspace("workspace.runs.read"),
        scopes=["{workspaceId}"],
    ),
]
RunManager = Annotated[
    User,
    Security(
        require_workspace("workspace.runs.manage"),
        scopes=["{workspaceId}"],
    ),
]

_COLUMN_FILTER_KEYS = {
    "sheet_name",
    "sheet_index",
    "table_index",
    "mapped_field",
    "mapping_status",
}
_RUN_EVENTS_FILENAME_STEM_MAX_LEN = 80


def _require_workspace_run(
    *,
    service: RunsService,
    workspace_id: UUID,
    run_id: UUID,
) -> Run:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _resolve_stream_cursor(request: Request, cursor: int | None) -> int:
    header_cursor = (request.headers.get("last-event-id") or "").strip()
    if header_cursor:
        try:
            parsed = int(header_cursor)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    if cursor is None:
        return 0
    return max(0, int(cursor))


def get_run_column_filters(
    request: Request,
    filters: Annotated[RunColumnFilters, Depends()],
) -> RunColumnFilters:
    allowed = _COLUMN_FILTER_KEYS
    extras = sorted({key for key in request.query_params.keys() if key not in allowed})
    if extras:
        detail = [
            {
                "type": "extra_forbidden",
                "loc": ["query", key],
                "msg": "Extra inputs are not permitted",
                "input": request.query_params.get(key),
            }
            for key in extras
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    return filters


def _output_not_ready_detail(message: str) -> dict[str, dict[str, str]]:
    return {
        "error": {
            "code": "OUTPUT_NOT_READY",
            "message": message,
        }
    }


def _run_failed_no_output_detail(message: str) -> dict[str, dict[str, str]]:
    return {
        "error": {
            "code": "RUN_FAILED_NO_OUTPUT",
            "message": message,
        }
    }


def _run_cancelled_no_output_detail(message: str) -> dict[str, dict[str, str]]:
    return {
        "error": {
            "code": "RUN_CANCELLED_NO_OUTPUT",
            "message": message,
        }
    }


def _engine_dependency_missing_detail(exc: ConfigEngineDependencyMissingError) -> dict[str, str]:
    detail = {"error": "engine_dependency_missing"}
    if getattr(exc, "detail", None):
        detail["detail"] = str(exc.detail)
    return detail


def _input_document_required_detail() -> dict[str, str]:
    return {"error": "input_document_required_for_process"}


def _output_missing_detail(*, run: Run, message: str) -> str | dict[str, dict[str, str]]:
    if run.status is RunStatus.FAILED:
        return _run_failed_no_output_detail(message)
    if run.status is RunStatus.CANCELLED:
        return _run_cancelled_no_output_detail(message)
    return message


def _normalise_run_events_filename_stem(value: str | None) -> str:
    if value is None:
        return ""
    candidate = value.strip()
    if not candidate:
        return ""
    filtered = "".join(ch for ch in candidate if unicodedata.category(ch)[0] != "C")
    collapsed = " ".join(filtered.split()).strip()
    if not collapsed:
        return ""
    if len(collapsed) > _RUN_EVENTS_FILENAME_STEM_MAX_LEN:
        collapsed = collapsed[:_RUN_EVENTS_FILENAME_STEM_MAX_LEN].rstrip()
    return collapsed


def _format_run_events_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=UTC)
    else:
        normalized = value.astimezone(UTC)
    return normalized.strftime("%Y%m%dT%H%M%SZ")


def _build_run_events_download_filename(*, run: Run, input_filename: str | None) -> str:
    source_stem = FilePath(input_filename).stem if input_filename else None
    stem = _normalise_run_events_filename_stem(source_stem)
    if not stem:
        stem = f"run-{str(run.id)[:8]}"
    timestamp = _format_run_events_timestamp(run.created_at)
    return f"{stem}_{timestamp}.ndjson"


@router.post(
    "",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
    summary="Create and enqueue a run",
    description=(
        "Create a run in the target workspace and enqueue it for worker processing. "
        "When `configuration_id` is omitted, the active workspace configuration is used."
    ),
)
def create_workspace_run_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceCreateRequest,
    service: RunsServiceDep,
    _actor: RunManager,
) -> RunResource:
    """Create a run for ``workspace_id`` and enqueue execution."""

    try:
        run = service.prepare_run_for_workspace(
            workspace_id=workspace_id,
            configuration_id=payload.configuration_id,
            input_document_id=payload.input_document_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputDocumentRequiredForProcessError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_input_document_required_detail(),
        ) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ConfigEngineDependencyMissingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_engine_dependency_missing_detail(exc),
        ) from exc
    except RunSafeModeEnabledError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SAFE_MODE_ENABLED",
                    "message": str(exc) or "Safe mode is enabled.",
                }
            },
        ) from exc

    return service.to_resource(run)


@router.post(
    "/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
    summary="Create and enqueue runs in batch",
    description=(
        "Create one run per document in `document_ids` and enqueue all runs as a single "
        "all-or-nothing operation."
    ),
)
def create_workspace_runs_batch_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceBatchCreateRequest,
    service: RunsServiceDep,
    _actor: RunManager,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``workspace_id`` and enqueue execution."""

    try:
        runs = service.prepare_runs_batch_for_workspace(
            workspace_id=workspace_id,
            configuration_id=payload.configuration_id,
            document_ids=payload.document_ids,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputDocumentRequiredForProcessError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_input_document_required_detail(),
        ) from exc
    except ConfigEngineDependencyMissingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_engine_dependency_missing_detail(exc),
        ) from exc
    except RunSafeModeEnabledError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SAFE_MODE_ENABLED",
                    "message": str(exc) or "Safe mode is enabled.",
                }
            },
        ) from exc

    resources = [service.to_resource(run) for run in runs]
    return RunBatchCreateResponse(runs=resources)


@router.get(
    "",
    response_model=RunPage,
    response_model_exclude_none=True,
    summary="List runs in a workspace",
    description=(
        "Return a cursor-paginated run list for the workspace with filtering, search, and sorting."
    ),
)
def list_workspace_runs_endpoint(
    workspace_id: WorkspacePath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> RunPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    return service.list_runs(
        workspace_id=workspace_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )


@router.get(
    "/{runId}",
    response_model=RunResource,
    summary="Get run details",
    description="Return a single run resource for the requested workspace and run identifier.",
)
def get_workspace_run_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> RunResource:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    return service.to_resource(run)


@router.post(
    "/{runId}/cancel",
    response_model=RunResource,
    dependencies=[Security(require_csrf)],
    summary="Cancel a run",
    description="Request cancellation for a run that is still cancellable.",
)
def cancel_workspace_run_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceDep,
    _actor: RunManager,
) -> RunResource:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        run = service.cancel_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunNotCancellableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return service.to_resource(run)


@router.get(
    "/{runId}/metrics",
    response_model=RunMetricsResource,
    response_model_exclude_none=True,
    summary="Get run metrics",
    description=(
        "Return derived run metrics from worker events, including evaluation, validation, and "
        "workbook statistics."
    ),
)
def get_workspace_run_metrics_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> RunMetricsResource:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        metrics = service.get_run_metrics(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if metrics is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run metrics not available")
    return RunMetricsResource.model_validate(metrics)


@router.get(
    "/{runId}/fields",
    response_model=list[RunFieldResource],
    response_model_exclude_none=True,
    summary="List run field detection results",
    description="Return field-level detection outcomes captured for the run.",
)
def list_workspace_run_fields_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> list[RunFieldResource]:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        fields = service.list_run_fields(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunFieldResource.model_validate(item) for item in fields]


@router.get(
    "/{runId}/columns",
    response_model=list[RunColumnResource],
    response_model_exclude_none=True,
    summary="List run column mappings",
    description="Return detected input columns and mapping metadata for the run.",
)
def list_workspace_run_columns_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    filters: Annotated[RunColumnFilters, Depends(get_run_column_filters)],
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> list[RunColumnResource]:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        columns = service.list_run_columns(run_id=run_id, filters=filters)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunColumnResource.model_validate(item) for item in columns]


@router.get(
    "/{runId}/input",
    response_model=RunInput,
    response_model_exclude_none=True,
    summary="Get run input metadata",
    description="Return the input document/version metadata associated with the run.",
)
def get_workspace_run_input_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> RunInput:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        return service.get_run_input_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{runId}/input/download",
    summary="Download run input file",
    description="Download the exact input file version used by this run.",
)
def download_workspace_run_input_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> StreamingResponse:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    blob_storage = get_storage_adapter(request)
    session_factory = get_session_factory(request)
    try:
        with session_factory() as session:
            local_service = RunsService(
                session=session,
                settings=settings,
                blob_storage=blob_storage,
            )
            _, document, version, stream = local_service.stream_run_input(run_id=run_id)
            media_type = version.content_type or "application/octet-stream"
            filename = version.filename_at_upload or document.name
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (RunDocumentMissingError, RunInputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = build_content_disposition(filename)
    return response


@router.get(
    "/{runId}/events/stream",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Run not found"}},
    summary="Stream run events (SSE)",
    description=(
        "Stream run events using Server-Sent Events. "
        "Use `cursor` or `Last-Event-ID` to resume from a prior position."
    ),
)
async def stream_workspace_run_events_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    request: Request,
    service: RunsServiceReadDep,
    _actor: RunReader,
    *,
    cursor: Annotated[
        int | None,
        Query(
            ge=0,
            description=(
                "Byte offset cursor for resuming from a prior stream position. "
                "When Last-Event-ID is present, that value takes precedence."
            ),
        ),
    ] = None,
) -> EventSourceResponse:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    resolved_cursor = _resolve_stream_cursor(request, cursor)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        async for message in service.stream_run_events(run_id=run.id, cursor=resolved_cursor):
            if await request.is_disconnected():
                return
            yield message

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{runId}/events/download",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Events unavailable"}},
    summary="Download run events (NDJSON log)",
    description="Download the persisted NDJSON event log for the run.",
)
def download_workspace_run_events_file_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> StreamingResponse:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    blob_storage = get_storage_adapter(request)
    session_factory = get_session_factory(request)
    input_filename: str | None = None
    try:
        with session_factory() as session:
            local_service = RunsService(
                session=session,
                settings=settings,
                blob_storage=blob_storage,
            )
            stream = local_service.stream_run_logs(run_id=run_id)
            try:
                input_metadata = local_service.get_run_input_metadata(run_id=run_id)
                input_filename = input_metadata.filename
            except (RunInputMissingError, RunDocumentMissingError):
                input_filename = None
    except (RunNotFoundError, RunLogsFileMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    filename = _build_run_events_download_filename(run=run, input_filename=input_filename)
    response = StreamingResponse(stream, media_type="application/x-ndjson")
    response.headers["Content-Disposition"] = build_content_disposition(filename)
    return response


@router.get(
    "/{runId}/output",
    response_model=RunOutput,
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
    },
    summary="Get run output metadata",
    description="Return output file metadata, readiness, and download link information.",
)
def get_workspace_run_output_metadata_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> RunOutput:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        return service.get_run_output_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{runId}/output",
    response_model=RunOutput,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or input document not found"},
        status.HTTP_409_CONFLICT: {"description": "Run output cannot be uploaded yet"},
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "description": "Uploaded file exceeds the configured size limit.",
        },
    },
    summary="Upload manual run output",
    description="Upload an output artifact for a run managed manually outside worker execution.",
)
def upload_workspace_run_output_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceDep,
    actor: RunManager,
    *,
    file: Annotated[UploadFile, File(...)],
) -> RunOutput:
    _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        return service.upload_manual_output(
            run_id=run_id,
            upload=file,
            actor_id=actor.id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_output_not_ready_detail(str(exc)),
        ) from exc
    except StorageLimitError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc


@router.get(
    "/{runId}/output/download",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
    },
    summary="Download run output file",
    description="Download the latest output file artifact associated with the run.",
)
def download_workspace_run_output_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> StreamingResponse:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    blob_storage = get_storage_adapter(request)
    session_factory = get_session_factory(request)
    try:
        with session_factory() as session:
            local_service = RunsService(
                session=session,
                settings=settings,
                blob_storage=blob_storage,
            )
            try:
                _, output_file, output_version, stream = local_service.stream_run_output(
                    run_id=run_id
                )
            except RunOutputNotReadyError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=_output_not_ready_detail(str(exc)),
                ) from exc
            except RunOutputMissingError as exc:
                detail = _output_missing_detail(run=run, message=str(exc))
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = output_version.content_type or "application/octet-stream"
    filename = output_version.filename_at_upload or output_file.name
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = build_content_disposition(filename)
    return response


@router.get(
    "/{runId}/output/sheets",
    response_model=list[RunOutputSheet],
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Sheets are not supported for this file type.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The output exists but could not be parsed for worksheets.",
        },
    },
    summary="List run output worksheets",
    description=(
        "List worksheets available in the run output artifact when sheet "
        "introspection is supported."
    ),
)
def list_workspace_run_output_sheets_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    service: RunsServiceReadDep,
    _actor: RunReader,
) -> list[RunOutputSheet]:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    try:
        return service.list_run_output_sheets(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_output_not_ready_detail(str(exc)),
        ) from exc
    except RunOutputMissingError as exc:
        detail = _output_missing_detail(run=run, message=str(exc))
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except RunOutputSheetUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except RunOutputSheetParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/{runId}/output/preview",
    response_model=WorkbookSheetPreview,
    response_model_exclude_none=True,
    summary="Preview run output worksheet",
    description=(
        "Return a bounded preview of run output worksheet data with optional sheet selection "
        "and trimming controls."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Preview is not supported for this file type.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The output exists but could not be parsed for preview.",
        },
    },
)
def preview_workspace_run_output_endpoint(
    workspace_id: WorkspacePath,
    run_id: RunPath,
    response: Response,
    service: RunsServiceReadDep,
    _actor: RunReader,
    *,
    max_rows: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PREVIEW_ROWS,
            alias="maxRows",
            description="Maximum rows per sheet to include in the preview.",
        ),
    ] = DEFAULT_PREVIEW_ROWS,
    max_columns: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PREVIEW_COLUMNS,
            alias="maxColumns",
            description="Maximum columns per sheet to include in the preview.",
        ),
    ] = DEFAULT_PREVIEW_COLUMNS,
    trim_empty_columns: Annotated[
        bool,
        Query(
            alias="trimEmptyColumns",
            description="If true, trims columns with no data within the preview window.",
        ),
    ] = False,
    trim_empty_rows: Annotated[
        bool,
        Query(
            alias="trimEmptyRows",
            description="If true, trims rows with no data within the preview window.",
        ),
    ] = False,
    sheet_name: Annotated[
        str | None,
        Query(
            alias="sheetName",
            description=(
                "Optional worksheet name to preview (defaults to the first sheet when omitted)."
            ),
        ),
    ] = None,
    sheet_index: Annotated[
        int | None,
        Query(
            ge=0,
            alias="sheetIndex",
            description=(
                "Optional worksheet index to preview "
                "(0-based, defaults to the first sheet when omitted)."
            ),
        ),
    ] = None,
) -> WorkbookSheetPreview:
    run = _require_workspace_run(service=service, workspace_id=workspace_id, run_id=run_id)
    if sheet_name and sheet_index is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sheetName and sheetIndex are mutually exclusive",
        )
    if sheet_name is None and sheet_index is None:
        sheet_index = 0
    try:
        response.headers["Cache-Control"] = "no-store"
        return service.get_run_output_preview(
            run_id=run_id,
            max_rows=max_rows,
            max_columns=max_columns,
            trim_empty_columns=trim_empty_columns,
            trim_empty_rows=trim_empty_rows,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_output_not_ready_detail(str(exc)),
        ) from exc
    except RunOutputMissingError as exc:
        detail = _output_missing_detail(run=run, message=str(exc))
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except RunOutputPreviewUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (RunOutputPreviewParseError, RunOutputPreviewSheetNotFoundError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
