"""HTTP routes for configuration metadata and lifecycle operations."""

from __future__ import annotations

import io
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from ade_api.api.deps import (
    SettingsDep,
    get_configurations_service,
    get_configurations_service_read,
)
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.common.downloads import build_content_disposition
from ade_api.common.etag import build_etag_token, format_etag, format_weak_etag
from ade_api.core.http import require_csrf, require_workspace
from ade_api.db import get_session_factory
from ade_db.models import User

from ..exceptions import (
    ConfigEngineDependencyMissingError,
    ConfigImportError,
    ConfigPublishConflictError,
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStateError,
    ConfigStorageNotFoundError,
    ConfigurationNotFoundError,
)
from ..http import ConfigurationIdPath, WorkspaceIdPath, raise_problem
from ..schemas import (
    ConfigurationCreate,
    ConfigurationHistoryScope,
    ConfigurationHistoryStatusFilter,
    ConfigurationImportGithubRequest,
    ConfigurationPage,
    ConfigurationRecord,
    ConfigurationReplaceGithubRequest,
    ConfigurationRestoreRequest,
    ConfigurationUpdateRequest,
    ConfigurationWorkspaceHistoryResponse,
)
from ..service import (
    ConfigurationsService,
    PreconditionFailedError,
    PreconditionRequiredError,
)
from ..sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ..storage import ConfigStorage

router = APIRouter()

UPLOAD_ARCHIVE_FIELD = File(...)

CONFIG_CREATE_BODY = Body(
    ...,
    description="Display name and template/clone source for the configuration.",
)
CONFIG_RESTORE_BODY = Body(
    ...,
    description="Restore source and optional metadata for creating a new draft.",
)
CONFIG_UPDATE_BODY = Body(
    ...,
    description="Update editable draft configuration metadata.",
)
CONFIG_IMPORT_GITHUB_BODY = Body(
    ...,
    description="Create a draft configuration from a public GitHub repository URL.",
)
CONFIG_REPLACE_GITHUB_BODY = Body(
    ...,
    description="Replace a draft configuration from a public GitHub repository URL.",
)

ConfigurationsServiceDep = Annotated[ConfigurationsService, Depends(get_configurations_service)]
ConfigurationsServiceReadDep = Annotated[
    ConfigurationsService, Depends(get_configurations_service_read)
]


def _engine_dependency_missing_detail(exc: ConfigEngineDependencyMissingError) -> dict[str, str]:
    detail = {"error": "engine_dependency_missing"}
    if exc.detail:
        detail["detail"] = exc.detail
    return detail


def _config_import_error_detail(exc: ConfigImportError) -> dict[str, str | int | bool]:
    detail: dict[str, str | int | bool] = {"__raw_detail__": True, "error": exc.code}
    if exc.limit is not None:
        detail["limit"] = exc.limit
    if exc.detail:
        detail["detail"] = exc.detail
    return detail


def _config_import_error_status(exc: ConfigImportError) -> int:
    if exc.code == "internal_error":
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    if exc.code == "archive_too_large" and exc.limit:
        return status.HTTP_413_CONTENT_TOO_LARGE
    if exc.code == "github_rate_limited":
        return status.HTTP_429_TOO_MANY_REQUESTS
    if exc.code == "github_download_failed":
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_400_BAD_REQUEST


@router.get(
    "/configurations",
    response_model=ConfigurationPage,
    response_model_exclude_none=True,
    summary="List configurations for a workspace",
)
def list_configurations(
    workspace_id: WorkspaceIdPath,
    service: ConfigurationsServiceReadDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    return service.list_configurations(
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
    "/configurations/history",
    response_model=ConfigurationWorkspaceHistoryResponse,
    response_model_exclude_none=True,
    summary="Retrieve workspace configuration timeline",
)
def read_workspace_configuration_history(
    workspace_id: WorkspaceIdPath,
    service: ConfigurationsServiceReadDep,
    focus_configuration_id: Annotated[UUID | None, Query(alias="focus_configuration_id")] = None,
    scope: Annotated[ConfigurationHistoryScope, Query()] = "workspace",
    status_filter: Annotated[
        ConfigurationHistoryStatusFilter, Query(alias="status_filter")
    ] = "all",
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ] = None,
) -> ConfigurationWorkspaceHistoryResponse:
    try:
        return service.list_workspace_configuration_history(
            workspace_id=workspace_id,
            focus_configuration_id=focus_configuration_id,
            scope=scope,
            status_filter=status_filter,
            cursor=cursor,
            limit=limit,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/configurations/{configurationId}",
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Retrieve configuration metadata",
)
def read_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    response: Response,
    service: ConfigurationsServiceReadDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = service.get_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    payload = ConfigurationRecord.model_validate(record)
    etag = format_weak_etag(build_etag_token(payload.id, payload.updated_at))
    if etag:
        response.headers["ETag"] = etag
    return payload


@router.post(
    "/configurations",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from a template or clone",
    response_model_exclude_none=True,
)
def create_configuration(
    workspace_id: WorkspaceIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    payload: ConfigurationCreate = CONFIG_CREATE_BODY,
) -> ConfigurationRecord:
    try:
        record = service.create_configuration(
            workspace_id=workspace_id,
            display_name=payload.display_name,
            source=payload.source,
            notes=payload.notes,
        )
    except ConfigSourceNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="source_not_found",
        ) from exc
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigEngineDependencyMissingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_engine_dependency_missing_detail(exc),
        ) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="publish_conflict",
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{configurationId}/restore",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Restore a previous configuration as a new draft",
    response_model_exclude_none=True,
)
def restore_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    payload: ConfigurationRestoreRequest = CONFIG_RESTORE_BODY,
) -> ConfigurationRecord:
    try:
        record = service.restore_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            payload=payload,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigSourceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="source_not_found") from exc
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="publish_conflict") from exc
    return ConfigurationRecord.model_validate(record)


@router.patch(
    "/configurations/{configurationId}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Update editable metadata for a draft configuration",
)
def update_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    payload: ConfigurationUpdateRequest = CONFIG_UPDATE_BODY,
) -> ConfigurationRecord:
    try:
        record = service.update_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            payload=payload,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/import",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from an uploaded archive",
    response_model_exclude_none=True,
)
def import_configuration(
    workspace_id: WorkspaceIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    display_name: Annotated[str, Form(min_length=1)],
    notes: Annotated[str | None, Form()] = None,
    file: UploadFile = UPLOAD_ARCHIVE_FIELD,
) -> ConfigurationRecord:
    try:
        archive = file.file.read()
        record = service.import_configuration_from_archive(
            workspace_id=workspace_id,
            display_name=display_name.strip(),
            archive=archive,
            notes=notes.strip() if notes is not None else None,
        )
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigEngineDependencyMissingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_engine_dependency_missing_detail(exc),
        ) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="publish_conflict") from exc
    except ConfigImportError as exc:
        raise HTTPException(
            _config_import_error_status(exc),
            detail=_config_import_error_detail(exc),
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/import/github",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from a GitHub repository URL",
    response_model_exclude_none=True,
)
def import_configuration_from_github(
    workspace_id: WorkspaceIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    payload: ConfigurationImportGithubRequest = CONFIG_IMPORT_GITHUB_BODY,
) -> ConfigurationRecord:
    try:
        record = service.import_configuration_from_github_url(
            workspace_id=workspace_id,
            display_name=payload.display_name,
            url=payload.url,
            notes=payload.notes,
        )
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigEngineDependencyMissingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_engine_dependency_missing_detail(exc),
        ) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="publish_conflict") from exc
    except ConfigImportError as exc:
        raise HTTPException(
            _config_import_error_status(exc),
            detail=_config_import_error_detail(exc),
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{configurationId}/archive",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Archive a draft or active configuration",
    response_model_exclude_none=True,
)
def archive_configuration_endpoint(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = service.archive_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ConfigurationRecord.model_validate(record)


@router.get(
    "/configurations/{configurationId}/export",
    responses={
        status.HTTP_200_OK: {"content": {"application/zip": {}}},
    },
    summary="Export a configuration archive",
    description="Export the selected configuration as a ZIP archive.",
)
def export_config(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    request: Request,
    settings: SettingsDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
    format: str = "zip",
) -> StreamingResponse:
    if format != "zip":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unsupported_format")
    try:
        session_factory = get_session_factory(request)
        with session_factory() as session:
            storage = ConfigStorage(settings=settings)
            service = ConfigurationsService(session=session, storage=storage)
            blob = service.export_zip(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
            )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    stream = io.BytesIO(blob)
    headers = {
        "Content-Disposition": build_content_disposition(f"{configuration_id}.zip"),
    }
    return StreamingResponse(stream, media_type="application/zip", headers=headers)


@router.put(
    "/configurations/{configurationId}/import",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Replace a draft configuration from an uploaded archive",
    response_model_exclude_none=True,
)
def replace_configuration_from_archive(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    request: Request,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    file: UploadFile = UPLOAD_ARCHIVE_FIELD,
) -> ConfigurationRecord:
    archive = file.file.read()
    try:
        record = service.replace_configuration_from_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=archive,
            if_match=request.headers.get("if-match"),
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="configuration_storage_missing",
        ) from exc
    except ConfigStateError as exc:
        raise_problem("configuration_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except PreconditionRequiredError:
        raise_problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        raise_problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigImportError as exc:
        raise HTTPException(
            _config_import_error_status(exc),
            detail=_config_import_error_detail(exc),
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.put(
    "/configurations/{configurationId}/import/github",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Replace a draft configuration from a GitHub repository URL",
    response_model_exclude_none=True,
)
def replace_configuration_from_github(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    request: Request,
    service: ConfigurationsServiceDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    payload: ConfigurationReplaceGithubRequest = CONFIG_REPLACE_GITHUB_BODY,
) -> ConfigurationRecord:
    try:
        record = service.replace_configuration_from_github_url(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            url=payload.url,
            if_match=request.headers.get("if-match"),
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="configuration_storage_missing",
        ) from exc
    except ConfigStateError as exc:
        raise_problem("configuration_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except PreconditionRequiredError:
        raise_problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        raise_problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigImportError as exc:
        raise HTTPException(
            _config_import_error_status(exc),
            detail=_config_import_error_detail(exc),
        ) from exc

    return ConfigurationRecord.model_validate(record)
