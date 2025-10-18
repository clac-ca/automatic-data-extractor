"""FastAPI routes for configuration metadata."""

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
from ade.features.auth.dependencies import require_authenticated, require_csrf
from ade.features.roles.dependencies import require_workspace
from ade.platform.responses import DefaultResponse

from ..users.models import User
from .exceptions import (
    ActiveConfigurationNotFoundError,
    ConfigurationColumnNotFoundError,
    ConfigurationColumnValidationError,
    ConfigurationNotFoundError,
    ConfigurationScriptValidationError,
    ConfigurationScriptVersionNotFoundError,
    ConfigurationScriptVersionOwnershipError,
)
from .schemas import (
    ConfigurationColumnBindingUpdate,
    ConfigurationColumnIn,
    ConfigurationColumnOut,
    ConfigurationCreate,
    ConfigurationRecord,
    ConfigurationScriptVersionIn,
    ConfigurationScriptVersionOut,
    ConfigurationUpdate,
)
from .dependencies import get_configurations_service
from .service import ConfigurationsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["configurations"],
    dependencies=[Security(require_authenticated)],
)

CONFIGURATION_CREATE_BODY = Body(...)
CONFIGURATION_UPDATE_BODY = Body(...)
CONFIGURATION_COLUMNS_BODY = Body(...)
CONFIGURATION_SCRIPT_BODY = Body(...)
CONFIGURATION_COLUMN_BINDING_BODY = Body(...)


@router.get(
    "/configurations",
    response_model=list[ConfigurationRecord],
    status_code=status.HTTP_200_OK,
    summary="List configurations for the active workspace",
    response_model_exclude_none=True,
)
async def list_configurations(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    is_active: bool | None = Query(None),
) -> list[ConfigurationRecord]:
    return await service.list_configurations(
        workspace_id=workspace_id,
        is_active=is_active,
    )


@router.post(
    "/configurations",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration",
    response_model_exclude_none=True,
)
async def create_configuration(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigurationCreate = CONFIGURATION_CREATE_BODY,
) -> ConfigurationRecord:
    try:
        return await service.create_configuration(
            workspace_id=workspace_id,
            title=payload.title,
            payload=payload.payload,
            clone_from_configuration_id=payload.clone_from_configuration_id,
            clone_from_active=payload.clone_from_active,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ActiveConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/configurations/active",
    response_model=list[ConfigurationRecord],
    status_code=status.HTTP_200_OK,
    summary="List active configurations",
    response_model_exclude_none=True,
)
async def list_active_configurations(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigurationRecord]:
    return await service.list_active_configurations(
        workspace_id=workspace_id,
    )


@router.get(
    "/configurations/{configuration_id}",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a configuration by identifier",
    response_model_exclude_none=True,
)
async def read_configuration(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        return await service.get_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/configurations/{configuration_id}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Replace a configuration",
    response_model_exclude_none=True,
)
async def replace_configuration(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigurationUpdate = CONFIGURATION_UPDATE_BODY,
) -> ConfigurationRecord:
    try:
        return await service.update_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            title=payload.title,
            payload=payload.payload,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/configurations/{configuration_id}",
    dependencies=[Security(require_csrf)],
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a configuration",
)
async def delete_configuration(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> DefaultResponse:
    try:
        await service.delete_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return DefaultResponse.success("Configuration deleted")


@router.post(
    "/configurations/{configuration_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Activate a configuration",
    response_model_exclude_none=True,
)
async def activate_configuration(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        return await service.activate_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/configurations/{configuration_id}/columns",
    response_model=list[ConfigurationColumnOut],
    status_code=status.HTTP_200_OK,
    summary="List columns for a configuration",
    response_model_exclude_none=True,
)
async def list_configuration_columns(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigurationColumnOut]:
    try:
        return await service.list_columns(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.put(
    "/configurations/{configuration_id}/columns",
    dependencies=[Security(require_csrf)],
    response_model=list[ConfigurationColumnOut],
    status_code=status.HTTP_200_OK,
    summary="Replace configuration columns",
    response_model_exclude_none=True,
)
async def replace_configuration_columns(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    columns: list[ConfigurationColumnIn] = CONFIGURATION_COLUMNS_BODY,
) -> list[ConfigurationColumnOut]:
    try:
        return await service.replace_columns(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            columns=columns,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationColumnValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ConfigurationScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationScriptVersionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.put(
    "/configurations/{configuration_id}/columns/{canonical_key}/binding",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationColumnOut,
    status_code=status.HTTP_200_OK,
    summary="Update column binding metadata",
    response_model_exclude_none=True,
)
async def update_configuration_column_binding(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    canonical_key: Annotated[
        str, Path(min_length=1, description="Column canonical key")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigurationColumnBindingUpdate = CONFIGURATION_COLUMN_BINDING_BODY,
) -> ConfigurationColumnOut:
    try:
        return await service.update_column_binding(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            canonical_key=canonical_key,
            binding=payload,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationColumnNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationColumnValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ConfigurationScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationScriptVersionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/configurations/{configuration_id}/scripts/{canonical_key}/versions",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationScriptVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration script version",
    response_model_exclude_none=True,
)
async def create_configuration_script_version(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    canonical_key: Annotated[
        str, Path(min_length=1, description="Canonical column key")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    response: Response,
    *,
    payload: ConfigurationScriptVersionIn = CONFIGURATION_SCRIPT_BODY,
) -> ConfigurationScriptVersionOut:
    try:
        script, etag = await service.create_script_version(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            canonical_key=canonical_key,
            payload=payload,
            actor_id=str(_actor.id),
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationScriptValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    response.headers["ETag"] = f'W/"{etag}"'
    return script


@router.get(
    "/configurations/{configuration_id}/scripts/{canonical_key}/versions",
    response_model=list[ConfigurationScriptVersionOut],
    status_code=status.HTTP_200_OK,
    summary="List configuration script versions",
    response_model_exclude_none=True,
)
async def list_configuration_script_versions(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    canonical_key: Annotated[
        str, Path(min_length=1, description="Canonical column key")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigurationScriptVersionOut]:
    try:
        return await service.list_script_versions(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            canonical_key=canonical_key,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/configurations/{configuration_id}/scripts/{canonical_key}/versions/{script_version_id}",
    response_model=ConfigurationScriptVersionOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a configuration script version",
    response_model_exclude_none=True,
)
async def get_configuration_script_version(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    canonical_key: Annotated[
        str, Path(min_length=1, description="Canonical column key")
    ],
    script_version_id: Annotated[
        str, Path(min_length=1, description="Script version identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    include_code: bool = Query(False, description="Include script code in the response"),
) -> ConfigurationScriptVersionOut:
    try:
        return await service.get_script_version(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            canonical_key=canonical_key,
            script_version_id=script_version_id,
            include_code=include_code,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ConfigurationScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/configurations/{configuration_id}/scripts/{canonical_key}/versions/{script_version_id}:validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationScriptVersionOut,
    status_code=status.HTTP_200_OK,
    summary="Revalidate a configuration script version",
    response_model_exclude_none=True,
)
async def validate_configuration_script_version(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    canonical_key: Annotated[
        str, Path(min_length=1, description="Canonical column key")
    ],
    script_version_id: Annotated[
        str, Path(min_length=1, description="Script version identifier")
    ],
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configurations.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    response: Response,
    *,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ConfigurationScriptVersionOut:
    try:
        script_record, etag = await service.validate_script_version(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            canonical_key=canonical_key,
            script_version_id=script_version_id,
            if_match=if_match,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConfigurationScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConfigurationScriptValidationError as exc:
        status_code = (
            status.HTTP_428_PRECONDITION_REQUIRED
            if if_match is None
            else status.HTTP_412_PRECONDITION_FAILED
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

    response.headers["ETag"] = f'W/"{etag}"'
    return script_record


__all__ = ["router"]
