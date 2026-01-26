"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import logging
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

from ade_api.api.deps import SettingsDep, get_idempotency_service, get_runs_service
from ade_api.common.downloads import build_content_disposition
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookSheetPreview,
)
from ade_api.core.auth import AuthenticatedPrincipal
from ade_api.db import get_sessionmaker
from ade_api.core.http import get_current_principal, require_authenticated, require_csrf
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.idempotency import (
    IdempotencyService,
    build_request_hash,
    build_scope_key,
    require_idempotency_key,
)
from ade_api.infra.storage import StorageLimitError
from ade_api.models import RunStatus

from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunOutputPreviewParseError,
    RunOutputPreviewSheetNotFoundError,
    RunOutputPreviewUnsupportedError,
    RunOutputSheetParseError,
    RunOutputSheetUnsupportedError,
)
from .filters import RunColumnFilters
from .schemas import (
    RunBatchCreateRequest,
    RunBatchCreateResponse,
    RunColumnResource,
    RunCreateRequest,
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
    tags=["runs"],
    dependencies=[Security(require_authenticated)],
)
runs_service_dependency = Depends(get_runs_service)
logger = logging.getLogger(__name__)

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
ConfigurationPath = Annotated[
    UUID,
    Path(
        description="Configuration identifier",
        alias="configurationId",
    ),
]
RunPath = Annotated[
    UUID,
    Path(
        description="Run identifier",
        alias="runId",
    ),
]

_COLUMN_FILTER_KEYS = {
    "sheet_name",
    "sheet_index",
    "table_index",
    "mapped_field",
    "mapping_status",
}


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


@router.post(
    "/configurations/{configurationId}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
def create_run_endpoint(
    *,
    configuration_id: ConfigurationPath,
    payload: RunCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``configuration_id`` and enqueue execution."""

    scope_key = build_scope_key(principal_id=str(principal.user_id))
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        run = service.prepare_run(
            configuration_id=configuration_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    resource = service.to_resource(run)
    idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=resource,
    )
    return resource


@router.post(
    "/configurations/{configurationId}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
def create_runs_batch_endpoint(
    *,
    configuration_id: ConfigurationPath,
    payload: RunBatchCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``configuration_id`` and enqueue execution."""

    scope_key = build_scope_key(principal_id=str(principal.user_id))
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        runs = service.prepare_runs_batch(
            configuration_id=configuration_id,
            document_ids=payload.document_ids,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    resources = [service.to_resource(run) for run in runs]
    response_payload = RunBatchCreateResponse(runs=resources)
    idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=response_payload,
    )
    return response_payload


@router.post(
    "/workspaces/{workspaceId}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
def create_workspace_run_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``workspace_id`` and enqueue execution."""

    scope_key = build_scope_key(
        principal_id=str(principal.user_id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

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
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    resource = service.to_resource(run)
    idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=resource,
    )
    return resource


@router.post(
    "/workspaces/{workspaceId}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
def create_workspace_runs_batch_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceBatchCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``workspace_id`` and enqueue execution."""

    scope_key = build_scope_key(
        principal_id=str(principal.user_id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

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

    resources = [service.to_resource(run) for run in runs]
    response_payload = RunBatchCreateResponse(runs=resources)
    idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=response_payload,
    )
    return response_payload


@router.get(
    "/configurations/{configurationId}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
def list_configuration_runs_endpoint(
    configuration_id: ConfigurationPath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    try:
        resolved_sort = resolve_cursor_sort(
            list_query.sort,
            allowed=SORT_FIELDS,
            cursor_fields=CURSOR_FIELDS,
            default=DEFAULT_SORT,
            id_field=ID_FIELD,
        )
        return service.list_runs_for_configuration(
            configuration_id=configuration_id,
            filters=list_query.filters,
            join_operator=list_query.join_operator,
            q=list_query.q,
            resolved_sort=resolved_sort,
            limit=list_query.limit,
            cursor=list_query.cursor,
            include_total=list_query.include_total,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/workspaces/{workspaceId}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
def list_workspace_runs_endpoint(
    workspace_id: WorkspacePath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    service: RunsService = runs_service_dependency,
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


@router.get("/runs/{runId}", response_model=RunResource)
def get_run_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunResource:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return service.to_resource(run)


@router.get(
    "/runs/{runId}/metrics",
    response_model=RunMetricsResource,
    response_model_exclude_none=True,
)
def get_run_metrics_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunMetricsResource:
    try:
        metrics = service.get_run_metrics(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if metrics is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run metrics not available")
    return RunMetricsResource.model_validate(metrics)


@router.get(
    "/runs/{runId}/fields",
    response_model=list[RunFieldResource],
    response_model_exclude_none=True,
)
def list_run_fields_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> list[RunFieldResource]:
    try:
        fields = service.list_run_fields(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunFieldResource.model_validate(item) for item in fields]


@router.get(
    "/runs/{runId}/columns",
    response_model=list[RunColumnResource],
    response_model_exclude_none=True,
)
def list_run_columns_endpoint(
    run_id: RunPath,
    filters: Annotated[RunColumnFilters, Depends(get_run_column_filters)],
    service: RunsService = runs_service_dependency,
) -> list[RunColumnResource]:
    try:
        columns = service.list_run_columns(run_id=run_id, filters=filters)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunColumnResource.model_validate(item) for item in columns]


@router.get(
    "/runs/{runId}/input",
    response_model=RunInput,
    response_model_exclude_none=True,
    summary="Get run input metadata",
)
def get_run_input_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunInput:
    try:
        return service.get_run_input_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/runs/{runId}/input/download",
    summary="Download run input file",
)
def download_run_input_endpoint(
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
) -> StreamingResponse:
    session_factory = get_sessionmaker(request)
    try:
        with session_factory() as session:
            service = RunsService(session=session, settings=settings)
            _, document, version, stream = service.stream_run_input(run_id=run_id)
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
    "/runs/{runId}/events/download",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Events unavailable"}},
    summary="Download run events (NDJSON log)",
)
def download_run_events_file_endpoint(
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
):
    session_factory = get_sessionmaker(request)
    try:
        with session_factory() as session:
            service = RunsService(session=session, settings=settings)
            stream = service.stream_run_logs(run_id=run_id)
    except (RunNotFoundError, RunLogsFileMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    filename = "events.ndjson"
    response = StreamingResponse(stream, media_type="application/x-ndjson")
    response.headers["Content-Disposition"] = build_content_disposition(filename)
    return response


@router.get(
    "/runs/{runId}/output",
    response_model=RunOutput,
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
    },
    summary="Get run output metadata",
)
def get_run_output_metadata_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunOutput:
    try:
        return service.get_run_output_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/runs/{runId}/output",
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
)
def upload_run_output_endpoint(
    run_id: RunPath,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: RunsService = runs_service_dependency,
    *,
    file: Annotated[UploadFile, File(...)],
) -> RunOutput:
    try:
        return service.upload_manual_output(
            run_id=run_id,
            upload=file,
            actor_id=principal.user_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "OUTPUT_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except StorageLimitError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc


@router.get(
    "/runs/{runId}/output/download",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
    },
    summary="Download run output file",
)
def download_run_output_endpoint(
    run_id: RunPath,
    request: Request,
    settings: SettingsDep,
):
    session_factory = get_sessionmaker(request)
    try:
        with session_factory() as session:
            service = RunsService(session=session, settings=settings)
            try:
                _, output_file, output_version, stream = service.stream_run_output(run_id=run_id)
            except RunOutputNotReadyError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "OUTPUT_NOT_READY",
                            "message": str(exc),
                        }
                    },
                ) from exc
            except RunOutputMissingError as exc:
                run_record = service.get_run(run_id)  # type: ignore[arg-type]
                if run_record and run_record.status is RunStatus.FAILED:
                    detail = {
                        "error": {
                            "code": "RUN_FAILED_NO_OUTPUT",
                            "message": str(exc),
                        }
                    }
                else:
                    detail = str(exc)
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = output_version.content_type or "application/octet-stream"
    filename = output_version.filename_at_upload or output_file.name
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = build_content_disposition(filename)
    return response


@router.get(
    "/runs/{runId}/output/sheets",
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
)
def list_run_output_sheets_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> list[RunOutputSheet]:
    try:
        return service.list_run_output_sheets(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "OUTPUT_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except RunOutputMissingError as exc:
        status_code = status.HTTP_404_NOT_FOUND
        run_record = service.get_run(run_id)  # type: ignore[arg-type]
        if run_record and run_record.status is RunStatus.FAILED:
            detail = {
                "error": {
                    "code": "RUN_FAILED_NO_OUTPUT",
                    "message": str(exc),
                }
            }
        else:
            detail = str(exc)
        raise HTTPException(status_code, detail=detail) from exc
    except RunOutputSheetUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except RunOutputSheetParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/runs/{runId}/output/preview",
    response_model=WorkbookSheetPreview,
    response_model_exclude_none=True,
    summary="Preview run output worksheet",
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
def preview_run_output_endpoint(
    run_id: RunPath,
    response: Response,
    service: RunsService = runs_service_dependency,
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
                "Optional worksheet name to preview "
                "(defaults to the first sheet when omitted)."
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
            detail={
                "error": {
                    "code": "OUTPUT_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except RunOutputMissingError as exc:
        status_code = status.HTTP_404_NOT_FOUND
        run_record = service.get_run(run_id)  # type: ignore[arg-type]
        if run_record and run_record.status is RunStatus.FAILED:
            detail = {
                "error": {
                    "code": "RUN_FAILED_NO_OUTPUT",
                    "message": str(exc),
                }
            }
        else:
            detail = str(exc)
        raise HTTPException(status_code, detail=detail) from exc
    except RunOutputPreviewUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (RunOutputPreviewParseError, RunOutputPreviewSheetNotFoundError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
