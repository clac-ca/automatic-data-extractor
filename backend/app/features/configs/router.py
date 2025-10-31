"""HTTP API for the file-backed configuration engine."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import PlainTextResponse

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.features.users.models import User
from backend.app.shared.core.schema import ErrorMessage

from .dependencies import get_config_service
from .exceptions import (
    ConfigActivationError,
    ConfigError,
    ConfigExportError,
    ConfigFileNotFoundError,
    ConfigFileOperationError,
    ConfigImportError,
    ConfigNotFoundError,
    ConfigSecretNotFoundError,
    ConfigStatusConflictError,
    ManifestInvalidError,
)
from .models import ConfigStatus
from .schemas import (
    ConfigCloneRequest,
    ConfigCreateRequest,
    ConfigRecord,
    ConfigSecretCreateRequest,
    ConfigSecretMetadata,
    ConfigUpdateRequest,
    ConfigValidationResponse,
    FileItem,
    Manifest,
    RenameColumnRequest,
)
from .service import ConfigService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/configs",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)

CONFIG_CREATE_BODY = Body(...)
CONFIG_UPDATE_BODY = Body(...)
CONFIG_CLONE_BODY = Body(...)
RENAME_BODY = Body(...)
SECRET_BODY = Body(...)
DEFAULT_CONFIG_TITLE = "Untitled Configuration"


def _map_exception(exc: ConfigError) -> HTTPException:
    if isinstance(exc, (ConfigNotFoundError, ConfigFileNotFoundError, ConfigSecretNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (ConfigStatusConflictError, ConfigActivationError)):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ManifestInvalidError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, (ConfigFileOperationError, ConfigImportError)):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ConfigExportError):
        return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/",
    response_model=list[ConfigRecord],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="List configuration bundles",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def list_configs(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    status_filter: list[str] | None = Query(default=None, alias="status"),
) -> list[ConfigRecord]:
    try:
        return await service.list_configs(
            workspace_id=workspace_id,
            statuses=status_filter or None,
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.post(
    "/",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration bundle",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def create_config(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigCreateRequest = CONFIG_CREATE_BODY,
    response: Response,
) -> ConfigRecord:
    title = payload.title or DEFAULT_CONFIG_TITLE
    try:
        record = await service.create_config(
            workspace_id=workspace_id,
            title=title,
            note=payload.note,
            from_config_id=payload.from_config_id,
            actor_id=str(actor.id),
        )
    except ConfigNotFoundError as exc:
        raise _map_exception(exc) from exc
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    response.headers[
        "Location"
    ] = f"/api/v1/workspaces/{workspace_id}/configs/{record.config_id}"
    return record


@router.get(
    "/active",
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the active configuration",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_active_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    record = await service.get_active_config(workspace_id=workspace_id)
    if record is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Workspace does not have an active configuration.",
        )
    return record


@router.get(
    "/{config_id}",
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Retrieve configuration metadata",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_config(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    try:
        return await service.get_config(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.patch(
    "/{config_id}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Update configuration metadata",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def update_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigUpdateRequest = CONFIG_UPDATE_BODY,
) -> ConfigRecord:
    fields_set = payload.model_fields_set
    status_change = payload.status if "status" in fields_set else None
    record: ConfigRecord | None = None

    try:
        if any(name in fields_set for name in ("title", "note", "version")):
            if "title" in fields_set and payload.title is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="title must not be empty if provided.",
                )
            if "version" in fields_set and payload.version is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="version must not be empty if provided.",
                )
            note_value = payload.note
            if "note" in fields_set and payload.note is None:
                note_value = ""
            record = await service.update_config(
                workspace_id=workspace_id,
                config_id=config_id,
                title=payload.title,
                note=note_value,
                version=payload.version,
            )

        if status_change is not None:
            try:
                desired_status = ConfigStatus(status_change.lower())
            except ValueError as exc:  # pragma: no cover - defensive validation
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported status value",
                ) from exc
            if desired_status is ConfigStatus.ACTIVE:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Use the activation endpoint to mark a configuration active.",
                )
            if desired_status is ConfigStatus.ARCHIVED:
                record = await service.archive_config(
                    workspace_id=workspace_id,
                    config_id=config_id,
                    actor_id=str(actor.id),
                )
            elif desired_status is ConfigStatus.INACTIVE:
                record = await service.unarchive_config(
                    workspace_id=workspace_id,
                    config_id=config_id,
                )
    except ConfigError as exc:
        raise _map_exception(exc) from exc

    if record is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No changes were requested.",
        )
    return record


@router.delete(
    "/{config_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    try:
        await service.delete_config(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{config_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Activate a configuration bundle",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def activate_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    try:
        return await service.activate_config(
            workspace_id=workspace_id,
            config_id=config_id,
            actor_id=str(actor.id),
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.get(
    "/{config_id}/manifest",
    response_model=Manifest,
    status_code=status.HTTP_200_OK,
    summary="Fetch manifest.json",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorMessage},
    },
)
async def read_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Manifest:
    try:
        return await service.get_manifest(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.put(
    "/{config_id}/manifest",
    dependencies=[Security(require_csrf)],
    response_model=Manifest,
    status_code=status.HTTP_200_OK,
    summary="Write manifest.json",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorMessage},
    },
)
async def write_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    manifest: Manifest,
) -> Manifest:
    try:
        return await service.put_manifest(
            workspace_id=workspace_id, config_id=config_id, manifest=manifest
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.get(
    "/{config_id}/files",
    response_model=list[FileItem],
    status_code=status.HTTP_200_OK,
    summary="List files within a configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_files(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[FileItem]:
    try:
        return await service.list_files(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.get(
    "/{config_id}/files/{path:path}",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
    summary="Read a file from the configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    path: Annotated[str, Path(min_length=1, description="Relative file path")],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> PlainTextResponse:
    try:
        content = await service.read_file(
            workspace_id=workspace_id, config_id=config_id, path=path
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.put(
    "/{config_id}/files/{path:path}",
    dependencies=[Security(require_csrf)],
    response_model=FileItem,
    status_code=status.HTTP_200_OK,
    summary="Write a text file into the configuration bundle",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def write_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    content: str = Body(..., media_type="text/plain"),
) -> FileItem:
    try:
        return await service.write_file(
            workspace_id=workspace_id,
            config_id=config_id,
            path=path,
            content=content,
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.delete(
    "/{config_id}/files/{path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file from the configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    try:
        await service.delete_file(workspace_id=workspace_id, config_id=config_id, path=path)
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{config_id}/rename",
    dependencies=[Security(require_csrf)],
    response_model=Manifest,
    status_code=status.HTTP_200_OK,
    summary="Rename a canonical column key",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def rename_column(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: RenameColumnRequest = RENAME_BODY,
) -> Manifest:
    try:
        return await service.rename_column(
            workspace_id=workspace_id,
            config_id=config_id,
            from_key=payload.from_key,
            to_key=payload.to_key,
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.post(
    "/import",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Import a configuration bundle from a zip archive",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def import_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    title: str | None = Form(default=None),
    note: str | None = Form(default=None),
    archive: UploadFile = File(...),
    response: Response,
) -> ConfigRecord:
    resolved_title = (title or archive.filename or DEFAULT_CONFIG_TITLE).strip()
    if not resolved_title:
        resolved_title = DEFAULT_CONFIG_TITLE
    resolved_note = note.strip() if note else None
    data = await archive.read()
    try:
        record = await service.import_config(
            workspace_id=workspace_id,
            title=resolved_title,
            archive_bytes=data,
            note=resolved_note,
            actor_id=str(actor.id),
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    response.headers[
        "Location"
    ] = f"/api/v1/workspaces/{workspace_id}/configs/{record.config_id}"
    return record


@router.get(
    "/{config_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export a configuration bundle as a zip archive",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorMessage},
    },
)
async def export_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    try:
        payload = await service.export_config(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    filename = f"{config_id}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type="application/zip", headers=headers)


@router.post(
    "/{config_id}/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate the configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def validate_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigValidationResponse:
    try:
        manifest, issues = await service.validate_config(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    return ConfigValidationResponse(manifest=manifest, issues=issues)


@router.post(
    "/{config_id}/clone",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a configuration bundle",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def clone_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigCloneRequest = CONFIG_CLONE_BODY,
    response: Response,
) -> ConfigRecord:
    try:
        record = await service.clone_config(
            workspace_id=workspace_id,
            source_config_id=config_id,
            title=payload.title,
            note=payload.note,
            actor_id=str(actor.id),
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    response.headers[
        "Location"
    ] = f"/api/v1/workspaces/{workspace_id}/configs/{record.config_id}"
    return record


@router.get(
    "/{config_id}/secrets",
    response_model=list[ConfigSecretMetadata],
    status_code=status.HTTP_200_OK,
    summary="List manifest secrets",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_secrets(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigSecretMetadata]:
    try:
        return await service.list_secrets(workspace_id=workspace_id, config_id=config_id)
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.post(
    "/{config_id}/secrets",
    dependencies=[Security(require_csrf)],
    response_model=ConfigSecretMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a manifest secret",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def upsert_secret(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigSecretCreateRequest = SECRET_BODY,
) -> ConfigSecretMetadata:
    try:
        return await service.put_secret(
            workspace_id=workspace_id,
            config_id=config_id,
            name=payload.name,
            value=payload.value,
            key_id=payload.key_id or "default",
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc


@router.delete(
    "/{config_id}/secrets/{name}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a manifest secret",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_secret(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    name: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    try:
        await service.delete_secret(
            workspace_id=workspace_id,
            config_id=config_id,
            name=name,
        )
    except ConfigError as exc:
        raise _map_exception(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
