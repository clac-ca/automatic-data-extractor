"""FastAPI router exposing config management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security, status

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.features.users.models import User
from backend.app.shared.core.schema import ErrorMessage

from .dependencies import get_configs_service
from .exceptions import (
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionNotFoundError,
    InvalidConfigManifestError,
)
from .schemas import (
    ConfigCreateRequest,
    ConfigRecord,
    ConfigSummary,
    ConfigVersionCreateRequest,
    ConfigVersionRecord,
)
from .service import ConfigsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/configs",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)

CONFIG_BODY = Body(..., description="Config creation payload")
VERSION_BODY = Body(..., description="Config version payload")


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
    payload: Annotated[ConfigCreateRequest, CONFIG_BODY],
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
        return await service.create_config(
            workspace_id=workspace_id,
            request=payload,
            actor=actor,
        )
    except ConfigSlugConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidConfigManifestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{config_id}",
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve config details",
    responses={
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
    payload: Annotated[ConfigVersionCreateRequest, VERSION_BODY],
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
        return await service.publish_version(
            workspace_id=workspace_id,
            config_id=config_id,
            request=payload,
            actor=actor,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidConfigManifestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


__all__ = ["router"]
