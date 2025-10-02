"""FastAPI routes for configuration metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import Body, Depends, HTTPException, Query, status

from app.core.responses import DefaultResponse
from ..auth.security import access_control
from ..workspaces.dependencies import require_workspace_context
from ..workspaces.routing import workspace_scoped_router
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_configurations_service
from .exceptions import ConfigurationNotFoundError
from .schemas import ConfigurationCreate, ConfigurationRecord, ConfigurationUpdate
from .service import ConfigurationsService

router = workspace_scoped_router(tags=["configurations"])

CONFIGURATION_CREATE_BODY = Body(...)
CONFIGURATION_UPDATE_BODY = Body(...)

WorkspaceContextDep = Annotated[WorkspaceContext, Depends(require_workspace_context)]
ConfigurationsReadServiceDep = Annotated[
    ConfigurationsService,
    Depends(
        access_control(
            permissions={"workspace:configurations:read"},
            require_workspace=True,
            service_dependency=get_configurations_service,
        )
    ),
]
ConfigurationsWriteServiceDep = Annotated[
    ConfigurationsService,
    Depends(
        access_control(
            permissions={"workspace:configurations:write"},
            require_workspace=True,
            service_dependency=get_configurations_service,
        )
    ),
]


@router.get(
    "/configurations",
    response_model=list[ConfigurationRecord],
    status_code=status.HTTP_200_OK,
    summary="List configurations for the active workspace",
    response_model_exclude_none=True,
)
async def list_configurations(
    _: WorkspaceContextDep,
    service: ConfigurationsReadServiceDep,
    *,
    document_type: str | None = Query(None),
    is_active: bool | None = Query(None),
) -> list[ConfigurationRecord]:
    return await service.list_configurations(
        document_type=document_type,
        is_active=is_active,
    )


@router.post(
    "/configurations",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration",
    response_model_exclude_none=True,
)
async def create_configuration(
    _: WorkspaceContextDep,
    service: ConfigurationsWriteServiceDep,
    *,
    payload: ConfigurationCreate = CONFIGURATION_CREATE_BODY,
) -> ConfigurationRecord:
    return await service.create_configuration(
        document_type=payload.document_type,
        title=payload.title,
        payload=payload.payload,
    )


@router.get(
    "/configurations/active",
    response_model=list[ConfigurationRecord],
    status_code=status.HTTP_200_OK,
    summary="List active configurations",
    response_model_exclude_none=True,
)
async def list_active_configurations(
    _: WorkspaceContextDep,
    service: ConfigurationsReadServiceDep,
    *,
    document_type: str | None = Query(None),
) -> list[ConfigurationRecord]:
    return await service.list_active_configurations(document_type=document_type)


@router.get(
    "/configurations/{configuration_id}",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a configuration by identifier",
    response_model_exclude_none=True,
)
async def read_configuration(
    configuration_id: str,
    _: WorkspaceContextDep,
    service: ConfigurationsReadServiceDep,
) -> ConfigurationRecord:
    try:
        return await service.get_configuration(configuration_id=configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/configurations/{configuration_id}",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Replace a configuration",
    response_model_exclude_none=True,
)
async def replace_configuration(
    configuration_id: str,
    _: WorkspaceContextDep,
    service: ConfigurationsWriteServiceDep,
    *,
    payload: ConfigurationUpdate = CONFIGURATION_UPDATE_BODY,
) -> ConfigurationRecord:
    try:
        return await service.update_configuration(
            configuration_id=configuration_id,
            title=payload.title,
            payload=payload.payload,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/configurations/{configuration_id}",
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a configuration",
)
async def delete_configuration(
    configuration_id: str,
    _: WorkspaceContextDep,
    service: ConfigurationsWriteServiceDep,
) -> DefaultResponse:
    try:
        await service.delete_configuration(configuration_id=configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DefaultResponse.success("Configuration deleted")


@router.post(
    "/configurations/{configuration_id}/activate",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Activate a configuration",
    response_model_exclude_none=True,
)
async def activate_configuration(
    configuration_id: str,
    _: WorkspaceContextDep,
    service: ConfigurationsWriteServiceDep,
) -> ConfigurationRecord:
    try:
        return await service.activate_configuration(configuration_id=configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
