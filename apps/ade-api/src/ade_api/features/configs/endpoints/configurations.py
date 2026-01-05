"""HTTP routes for configuration metadata and lifecycle operations."""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from ade_api.api.deps import get_configurations_service, get_runs_service
from ade_api.common.downloads import build_content_disposition
from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.listing import ListQueryParams, list_query_params, strict_list_query_guard
from ade_api.common.sorting import resolve_sort
from ade_api.core.http import require_csrf, require_workspace
from ade_api.features.runs.service import RunsService
from ade_api.models import User

from ..etag import format_etag
from ..exceptions import (
    ConfigImportError,
    ConfigPublishConflictError,
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStateError,
    ConfigStorageNotFoundError,
    ConfigurationNotFoundError,
    ConfigValidationFailedError,
)
from ..http import ConfigurationIdPath, WorkspaceIdPath, raise_problem
from ..schemas import (
    ConfigurationCreate,
    ConfigurationPage,
    ConfigurationRecord,
    ConfigurationValidateResponse,
)
from ..service import (
    ConfigurationsService,
    PreconditionFailedError,
    PreconditionRequiredError,
)
from ..sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter()

UPLOAD_ARCHIVE_FIELD = File(...)

CONFIG_CREATE_BODY = Body(
    ...,
    description="Display name and template/clone source for the configuration.",
)
MAKE_ACTIVE_BODY = Body(
    None,
    description="Make the configuration active (archives any existing active configuration).",
)


@router.get(
    "/configurations",
    response_model=ConfigurationPage,
    response_model_exclude_none=True,
    summary="List configurations for a workspace",
)
async def list_configurations(
    workspace_id: WorkspaceIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationPage:
    order_by = resolve_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    return await service.list_configurations(
        workspace_id=workspace_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        order_by=order_by,
        page=list_query.page,
        per_page=list_query.per_page,
    )


@router.get(
    "/configurations/{configurationId}",
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Retrieve configuration metadata",
)
async def read_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    response: Response,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = await service.get_configuration(
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
async def create_configuration(
    workspace_id: WorkspaceIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
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
        record = await service.create_configuration(
            workspace_id=workspace_id,
            display_name=payload.display_name,
            source=payload.source,
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
    except ConfigPublishConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="publish_conflict",
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/import",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from an uploaded archive",
    response_model_exclude_none=True,
)
async def import_configuration(
    workspace_id: WorkspaceIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    *,
    display_name: Annotated[str, Form(min_length=1)],
    file: UploadFile = UPLOAD_ARCHIVE_FIELD,
) -> ConfigurationRecord:
    try:
        archive = await file.read()
        record = await service.import_configuration_from_archive(
            workspace_id=workspace_id,
            display_name=display_name.strip(),
            archive=archive,
        )
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="publish_conflict") from exc
    except ConfigImportError as exc:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.code == "archive_too_large" and exc.limit
            else status.HTTP_400_BAD_REQUEST
        )
        detail: str | dict = exc.code
        if exc.limit:
            detail = {"error": exc.code, "limit": exc.limit}
        raise HTTPException(status_code, detail=detail) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{configurationId}/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationValidateResponse,
    summary="Validate the configuration on disk",
    response_model_exclude_none=True,
)
async def validate_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationValidateResponse:
    try:
        result = await service.validate_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="configuration_storage_missing"
        ) from exc

    payload = ConfigurationValidateResponse(
        id=result.configuration.id,
        workspace_id=workspace_id,
        status=result.configuration.status,
        content_digest=result.content_digest,
        issues=result.issues,
    )
    return payload


@router.post(
    "/configurations/{configurationId}/publish",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Make a draft configuration active",
    response_model_exclude_none=True,
)
async def publish_configuration_endpoint(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    runs_service: Annotated[RunsService, Depends(get_runs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    payload: None = MAKE_ACTIVE_BODY,
) -> ConfigurationRecord:
    del payload
    try:
        record = await service.make_active_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="configuration_storage_missing",
        ) from exc
    except ConfigValidationFailedError as exc:
        detail = {
            "error": "validation_failed",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await runs_service.enqueue_pending_runs_for_configuration(
        configuration_id=record.id,
    )

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{configurationId}/archive",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Archive the active configuration",
    response_model_exclude_none=True,
)
async def archive_configuration_endpoint(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = await service.archive_configuration(
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
)
async def export_config(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
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
        blob = await service.export_zip(
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
async def replace_configuration_from_archive(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    file: UploadFile = UPLOAD_ARCHIVE_FIELD,
) -> ConfigurationRecord:
    archive = await file.read()
    try:
        record = await service.replace_configuration_from_archive(
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
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.code == "archive_too_large" and exc.limit
            else status.HTTP_400_BAD_REQUEST
        )
        detail: str | dict = exc.code
        if exc.limit:
            detail = {"error": exc.code, "limit": exc.limit}
        raise HTTPException(status_code, detail=detail) from exc

    return ConfigurationRecord.model_validate(record)
