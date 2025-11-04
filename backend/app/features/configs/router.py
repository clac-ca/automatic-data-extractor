"""FastAPI router exposing config management endpoints."""

import io
from typing import Annotated, Any

import json
from json import JSONDecodeError

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.features.users.models import User
from backend.app.shared.core.schema import ErrorMessage

from .dependencies import get_configs_service
from .exceptions import (
    ConfigActivationError,
    ConfigDraftConflictError,
    ConfigDraftFileTypeError,
    ConfigDraftNotFoundError,
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionNotFoundError,
    InvalidConfigManifestError,
)
from .schemas import (
    ConfigDraftCreateRequest,
    ConfigDraftPublishRequest,
    ConfigDraftRecord,
    ConfigFileContent,
    ConfigFileUpdate,
    ConfigPackageEntry,
    ConfigRecord,
    ConfigSummary,
    ConfigValidationResponse,
    ConfigVersionRecord,
    ValidationDiagnostic,
)
from .service import ConfigsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/configs",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)


def _manifest_error_detail(exc: InvalidConfigManifestError) -> Any:
    diagnostics = getattr(exc, "diagnostics", None) or []
    if diagnostics:
        return {
            "message": str(exc),
            "diagnostics": [
                _serialize_diagnostic(item) for item in diagnostics
            ],
        }
    return str(exc)


def _serialize_diagnostic(item: Any) -> dict[str, Any]:
    level = getattr(item, "level", "error")
    if hasattr(level, "value"):
        level_value = level.value
    else:
        level_value = str(level)
    return {
        "path": getattr(item, "path", ""),
        "code": getattr(item, "code", ""),
        "message": getattr(item, "message", ""),
        "level": level_value,
        "hint": getattr(item, "hint", None),
    }


@router.get(
    "",
    response_model=list[ConfigSummary],
    status_code=status.HTTP_200_OK,
    summary="List configs for a workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def list_configs(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted: Annotated[
        bool,
        Query(
            description="Include archived configs in the response",
        ),
    ] = False,
) -> list[ConfigSummary]:
    return await service.list_configs(
        workspace_id=workspace_id,
        include_deleted=include_deleted,
    )


@router.post(
    "/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate a config package",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
    },
)
async def validate_config_package(
    workspace_id: Annotated[str, Path(min_length=1)],
    manifest_json: Annotated[str, Form(description="Manifest JSON payload")],
    package: Annotated[UploadFile, File(description="Config package zip")],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigValidationResponse:
    try:
        manifest = json.loads(manifest_json)
    except JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest field must be valid JSON") from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest must be a JSON object")

    package_bytes = await package.read()
    await package.close()
    if not package_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Config package file is empty")

    diagnostics = await service.validate_package(manifest=manifest, package_bytes=package_bytes)
    return ConfigValidationResponse(diagnostics=[ValidationDiagnostic.model_validate(_serialize_diagnostic(item)) for item in diagnostics])


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a config and initial version",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    slug: Annotated[str, Form(min_length=1, max_length=100)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    manifest_json: Annotated[str, Form(description="Manifest JSON payload")],
    package: Annotated[UploadFile, File(description="Config package zip")],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    description: Annotated[str | None, Form(max_length=2000)] = None,
) -> ConfigRecord:
    try:
        manifest = json.loads(manifest_json)
    except JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest field must be valid JSON") from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest must be a JSON object")

    package_bytes = await package.read()
    await package.close()
    if not package_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Config package file is empty")

    try:
        return await service.create_config(
            workspace_id=workspace_id,
            slug=slug,
            title=title,
            description=description,
            manifest=manifest,
            package_filename=package.filename or "config.zip",
            package_bytes=package_bytes,
            actor=actor,
        )
    except ConfigSlugConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidConfigManifestError as exc:
        detail = _manifest_error_detail(exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get(
    "/{config_id}",
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve config details",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted_versions: Annotated[
        bool,
        Query(
            description="Include archived versions in the response",
        ),
    ] = False,
) -> ConfigRecord:
    try:
        return await service.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted_versions=include_deleted_versions,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/versions",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new config version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def publish_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    manifest_json: Annotated[str, Form(description="Manifest JSON payload")],
    package: Annotated[UploadFile, File(description="Config package zip")],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    label: Annotated[str | None, Form(max_length=50)] = None,
) -> ConfigVersionRecord:
    try:
        manifest = json.loads(manifest_json)
    except JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest field must be valid JSON") from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Manifest must be a JSON object")

    package_bytes = await package.read()
    await package.close()
    if not package_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Config package file is empty")

    try:
        return await service.publish_version(
            workspace_id=workspace_id,
            config_id=config_id,
            label=label,
            manifest=manifest,
            package_filename=package.filename or "config.zip",
            package_bytes=package_bytes,
            actor=actor,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidConfigManifestError as exc:
        detail = _manifest_error_detail(exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get(
    "/{config_id}/versions",
    response_model=list[ConfigVersionRecord],
    status_code=status.HTTP_200_OK,
    summary="List config versions",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_versions(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted: Annotated[
        bool,
        Query(
            description="Include archived versions",
        ),
    ] = False,
) -> list[ConfigVersionRecord]:
    try:
        return await service.list_versions(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=include_deleted,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/versions/{config_version_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Activate a config version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def activate_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    try:
        return await service.activate_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            actor=actor,
        )
    except ConfigActivationError as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        diagnostics = getattr(exc, "diagnostics", [])
        if diagnostics:
            detail["diagnostics"] = diagnostics
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{config_id}/versions/{config_version_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a config version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def archive_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.archive_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/versions/{config_version_id}/restore",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived config version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def restore_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionRecord:
    try:
        return await service.restore_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{config_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a config",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def archive_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.archive_config(
            workspace_id=workspace_id,
            config_id=config_id,
            actor=actor,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/restore",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Restore a config",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def restore_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    try:
        return await service.restore_config(
            workspace_id=workspace_id,
            config_id=config_id,
            actor=actor,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{config_id}/drafts",
    response_model=list[ConfigDraftRecord],
    status_code=status.HTTP_200_OK,
    summary="List drafts for a config",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_config_drafts(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigDraftRecord]:
    try:
        return await service.list_drafts(workspace_id=workspace_id, config_id=config_id)
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/drafts",
    dependencies=[Security(require_csrf)],
    response_model=ConfigDraftRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft from an existing config version",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def create_config_draft(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    payload: ConfigDraftCreateRequest,
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigDraftRecord:
    try:
        return await service.create_draft(
            workspace_id=workspace_id,
            config_id=config_id,
            base_config_version_id=payload.base_config_version_id,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidConfigManifestError as exc:
        detail = _manifest_error_detail(exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get(
    "/{config_id}/drafts/{draft_id}",
    response_model=ConfigDraftRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a draft",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_config_draft(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigDraftRecord:
    try:
        return await service.get_draft(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{config_id}/drafts/{draft_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a draft",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def delete_config_draft(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.delete_draft(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{config_id}/drafts/{draft_id}/files",
    response_model=list[ConfigPackageEntry],
    status_code=status.HTTP_200_OK,
    summary="List files within a draft",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_config_draft_files(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigPackageEntry]:
    try:
        return await service.list_draft_entries(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{config_id}/drafts/{draft_id}/files/{file_path:path}",
    response_model=ConfigFileContent,
    status_code=status.HTTP_200_OK,
    summary="Read a draft file",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorMessage},
    },
)
async def read_config_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigFileContent:
    try:
        return await service.read_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
            path=file_path,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError, FileNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigDraftFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc


@router.put(
    "/{config_id}/drafts/{draft_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigFileContent,
    status_code=status.HTTP_200_OK,
    summary="Write a draft file",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorMessage},
    },
)
async def write_config_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    payload: ConfigFileUpdate,
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigFileContent:
    try:
        return await service.write_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
            path=file_path,
            payload=payload,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError, FileNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigDraftConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ConfigDraftFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc


@router.delete(
    "/{config_id}/drafts/{draft_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a draft file or directory",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def delete_config_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.delete_draft_entry(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
            path=file_path,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError, FileNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/drafts/{draft_id}/publish",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a draft as a new config version",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def publish_config_draft(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    payload: ConfigDraftPublishRequest,
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionRecord:
    try:
        return await service.publish_draft(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
            label=payload.label,
            actor=actor,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidConfigManifestError as exc:
        detail = _manifest_error_detail(exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get(
    "/{config_id}/drafts/{draft_id}/download",
    summary="Download a draft as a ZIP archive",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def download_config_draft(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    draft_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> StreamingResponse:
    try:
        filename, payload = await service.export_draft_archive(
            workspace_id=workspace_id,
            config_id=config_id,
            draft_id=draft_id,
        )
    except (ConfigNotFoundError, ConfigDraftNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    stream = io.BytesIO(payload)
    return StreamingResponse(
        stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
