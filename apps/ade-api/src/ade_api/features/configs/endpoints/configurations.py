"""HTTP routes for configuration metadata and lifecycle operations."""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from ade_api.api.deps import SettingsDep, get_builds_service, get_configurations_service
from ade_api.common.downloads import build_content_disposition
from ade_api.common.pagination import PageParams, paginate_sequence
from ade_api.core.http import require_csrf, require_workspace
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildDecision, BuildsService
from ade_api.features.builds.tasks import execute_build_background
from ade_api.features.runs.tasks import enqueue_pending_runs_background
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
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationPage:
    records = await service.list_configurations(workspace_id=workspace_id)
    items = [ConfigurationRecord.model_validate(record) for record in records]
    page_result = paginate_sequence(
        items,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return ConfigurationPage(**page_result.model_dump())


@router.get(
    "/configurations/{configuration_id}",
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Retrieve configuration metadata",
)
async def read_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspace_id}"],
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
    return ConfigurationRecord.model_validate(record)


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
            scopes=["{workspace_id}"],
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
            scopes=["{workspace_id}"],
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
    "/configurations/{configuration_id}/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationValidateResponse,
    summary="Validate the configuration on disk",
    response_model_exclude_none=True,
)
async def validate_configuration(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    builds_service: Annotated[BuildsService, Depends(get_builds_service)],
    background_tasks: BackgroundTasks,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
    ) -> ConfigurationValidateResponse:
    try:
        workspace_uuid = workspace_id
        configuration_uuid = configuration_id
        build, context = await builds_service.ensure_build_for_run(
            workspace_id=workspace_uuid,
            configuration_id=configuration_uuid,
            force_rebuild=False,
            run_id=None,
            reason="validation",
        )
        if context.decision is BuildDecision.START_NEW:
            background_tasks.add_task(
                execute_build_background,
                context.as_dict(),
                BuildCreateOptions(force=False, wait=False).model_dump(),
                builds_service.settings.model_dump(mode="python"),
            )
        _ = build

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
    "/configurations/{configuration_id}/publish",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Make a draft configuration active",
    response_model_exclude_none=True,
)
async def publish_configuration_endpoint(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
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

    background_tasks.add_task(
        enqueue_pending_runs_background,
        workspace_id=workspace_id,
        configuration_id=record.id,
        settings_payload=settings.model_dump(mode="python"),
    )

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{configuration_id}/archive",
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
            scopes=["{workspace_id}"],
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
    "/configurations/{configuration_id}/export",
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
            scopes=["{workspace_id}"],
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
    "/configurations/{configuration_id}/import",
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
            scopes=["{workspace_id}"],
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
