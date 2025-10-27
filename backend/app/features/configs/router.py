"""FastAPI router exposing configuration versioning APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.shared.core.responses import DefaultResponse
from backend.app.shared.core.schema import ErrorMessage

from ..users.models import User
from .dependencies import (
    get_config_file_service,
    get_config_service,
    get_manifest_service,
)
from .exceptions import (
    ConfigNotFoundError,
    ConfigPublishConflictError,
    ConfigRevertUnavailableError,
    ConfigSlugConflictError,
    DraftFileConflictError,
    DraftFileNotFoundError,
    DraftVersionNotFoundError,
    ManifestValidationError,
)
from .schemas import (
    ConfigCreateRequest,
    ConfigFileContent,
    ConfigFileCreateRequest,
    ConfigFileSummary,
    ConfigFileUpdateRequest,
    ConfigPublishRequest,
    ConfigRecord,
    ConfigRevertRequest,
    ConfigVersionRecord,
    ManifestPatchRequest,
    ManifestResponse,
)
from .service import ConfigFileService, ConfigService, ManifestService

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)

CONFIG_CREATE_BODY = Body(...)
CONFIG_PUBLISH_BODY = Body(...)
CONFIG_REVERT_BODY = Body(default=ConfigRevertRequest())
CONFIG_FILE_CREATE_BODY = Body(...)
CONFIG_FILE_UPDATE_BODY = Body(...)
MANIFEST_PATCH_BODY = Body(...)


@router.get(
    "/configs",
    response_model=list[ConfigRecord],
    status_code=status.HTTP_200_OK,
    summary="List configuration packages for a workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def list_configs(
    workspace_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigRecord]:
    return await service.list_configs(workspace_id=workspace_id)


@router.post(
    "/configs",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration package",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_config(
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
    payload: ConfigCreateRequest = CONFIG_CREATE_BODY,
) -> ConfigRecord:
    try:
        return await service.create_config(
            workspace_id=workspace_id,
            slug=payload.slug,
            title=payload.title,
            actor_id=str(actor.id),
        )
    except ConfigSlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/configs/{config_id}",
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve configuration details",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_config(
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
) -> ConfigRecord:
    try:
        return await service.get_config(workspace_id=workspace_id, config_id=config_id)
    except (ConfigNotFoundError, DraftVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/configs/{config_id}",
    dependencies=[Security(require_csrf)],
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a configuration package",
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
    *,
    force: bool = Query(False, description="Force delete even when published versions exist."),
) -> DefaultResponse:
    try:
        await service.delete_config(
            workspace_id=workspace_id,
            config_id=config_id,
            force=force,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return DefaultResponse.success("Configuration deleted")


@router.get(
    "/configs/{config_id}/versions",
    response_model=list[ConfigVersionRecord],
    status_code=status.HTTP_200_OK,
    summary="List versions for a configuration",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_versions(
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
) -> list[ConfigVersionRecord]:
    try:
        return await service.list_versions(workspace_id=workspace_id, config_id=config_id)
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/configs/{config_id}/publish",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Publish the draft configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def publish_config(
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
    payload: ConfigPublishRequest = CONFIG_PUBLISH_BODY,
) -> ConfigVersionRecord:
    try:
        return await service.publish_draft(
            workspace_id=workspace_id,
            config_id=config_id,
            semver=payload.semver,
            message=payload.message,
            actor_id=str(actor.id),
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/configs/{config_id}/revert",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Revert to the previously published configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def revert_config(
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
    payload: ConfigRevertRequest = CONFIG_REVERT_BODY,
) -> ConfigVersionRecord:
    try:
        return await service.revert_published(
            workspace_id=workspace_id,
            config_id=config_id,
            message=payload.message,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConfigRevertUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/configs/{config_id}/draft/files",
    response_model=list[ConfigFileSummary],
    status_code=status.HTTP_200_OK,
    summary="List files within the draft version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_draft_files(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigFileService, Depends(get_config_file_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigFileSummary]:
    try:
        return await service.list_draft_files(workspace_id=workspace_id, config_id=config_id)
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/configs/{config_id}/draft/files",
    dependencies=[Security(require_csrf)],
    response_model=ConfigFileContent,
    status_code=status.HTTP_201_CREATED,
    summary="Create a file in the draft version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
    },
)
async def create_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigFileService, Depends(get_config_file_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigFileCreateRequest = CONFIG_FILE_CREATE_BODY,
) -> ConfigFileContent:
    initial_code = payload.template or ""
    try:
        return await service.create_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            path=payload.path,
            code=initial_code,
            language=payload.language,
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError, ManifestValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DraftFileConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc


@router.get(
    "/configs/{config_id}/draft/files/{file_path:path}",
    response_model=ConfigFileContent,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a draft file",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigFileService, Depends(get_config_file_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    response: Response,
) -> ConfigFileContent:
    try:
        record = await service.get_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            path=file_path,
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError, DraftFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    response.headers["ETag"] = record.sha256
    return record


@router.put(
    "/configs/{config_id}/draft/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigFileContent,
    status_code=status.HTTP_200_OK,
    summary="Update a draft file with optimistic locking",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
    },
)
async def update_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigFileService, Depends(get_config_file_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigFileUpdateRequest = CONFIG_FILE_UPDATE_BODY,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ConfigFileContent:
    expected_sha = if_match.strip() if if_match else None
    try:
        return await service.update_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            path=file_path,
            code=payload.code,
            expected_sha=expected_sha,
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError, DraftFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DraftFileConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc


@router.delete(
    "/configs/{config_id}/draft/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a draft file",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def delete_draft_file(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    file_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigFileService, Depends(get_config_file_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> DefaultResponse:
    try:
        await service.delete_draft_file(
            workspace_id=workspace_id,
            config_id=config_id,
            path=file_path,
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError, DraftFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return DefaultResponse.success("Draft file deleted")


@router.get(
    "/configs/{config_id}/draft/manifest",
    response_model=ManifestResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the draft manifest",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ManifestService, Depends(get_manifest_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ManifestResponse:
    try:
        return await service.get_manifest(workspace_id=workspace_id, config_id=config_id)
    except (ConfigNotFoundError, DraftVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/configs/{config_id}/draft/manifest",
    dependencies=[Security(require_csrf)],
    response_model=ManifestResponse,
    status_code=status.HTTP_200_OK,
    summary="Patch the draft manifest",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
    },
)
async def patch_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ManifestService, Depends(get_manifest_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ManifestPatchRequest = MANIFEST_PATCH_BODY,
) -> ManifestResponse:
    try:
        return await service.patch_manifest(
            workspace_id=workspace_id,
            config_id=config_id,
            payload=payload,
        )
    except (ConfigNotFoundError, DraftVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/configs/{config_id}/draft:plan",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Generate an execution plan for the draft version",
)
async def plan_draft(
    _workspace_id: Annotated[str, Path(min_length=1)],
    _config_id: Annotated[str, Path(min_length=1)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Draft planning is not implemented yet.",
    )


@router.post(
    "/configs/{config_id}/draft:dry-run",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Run a draft dry-run against a document",
)
async def dry_run_draft(
    _workspace_id: Annotated[str, Path(min_length=1)],
    _config_id: Annotated[str, Path(min_length=1)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Draft dry-run is not implemented yet.",
    )


__all__ = ["router"]
