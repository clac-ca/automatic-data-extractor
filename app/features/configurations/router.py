"""FastAPI routes for configuration metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import DefaultResponse
from app.db.session import get_session

from ..workspaces.dependencies import require_workspace_access
from ..workspaces.schemas import WorkspaceProfile
from .exceptions import ConfigurationNotFoundError
from .schemas import ConfigurationCreate, ConfigurationRecord, ConfigurationUpdate
from .service import ConfigurationsService

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["configurations"])

CONFIGURATION_CREATE_BODY = Body(...)
CONFIGURATION_UPDATE_BODY = Body(...)


@router.get(
    "/configurations",
    response_model=list[ConfigurationRecord],
    status_code=status.HTTP_200_OK,
    summary="List configurations for the active workspace",
    response_model_exclude_none=True,
)
async def list_configurations(
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    document_type: str | None = Query(None),
    is_active: bool | None = Query(None),
) -> list[ConfigurationRecord]:
    service = ConfigurationsService(session=session)
    return await service.list_configurations(
        workspace_id=workspace.workspace_id,
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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.ReadWrite"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: ConfigurationCreate = CONFIGURATION_CREATE_BODY,
) -> ConfigurationRecord:
    service = ConfigurationsService(session=session)
    return await service.create_configuration(
        workspace_id=workspace.workspace_id,
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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    document_type: str | None = Query(None),
) -> list[ConfigurationRecord]:
    service = ConfigurationsService(session=session)
    return await service.list_active_configurations(
        workspace_id=workspace.workspace_id,
        document_type=document_type,
    )


@router.get(
    "/configurations/{configuration_id}",
    response_model=ConfigurationRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a configuration by identifier",
    response_model_exclude_none=True,
)
async def read_configuration(
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigurationRecord:
    service = ConfigurationsService(session=session)
    try:
        return await service.get_configuration(
            workspace_id=workspace.workspace_id,
            configuration_id=configuration_id,
        )
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
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.ReadWrite"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: ConfigurationUpdate = CONFIGURATION_UPDATE_BODY,
) -> ConfigurationRecord:
    service = ConfigurationsService(session=session)
    try:
        return await service.update_configuration(
            workspace_id=workspace.workspace_id,
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
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.ReadWrite"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DefaultResponse:
    service = ConfigurationsService(session=session)
    try:
        await service.delete_configuration(
            workspace_id=workspace.workspace_id,
            configuration_id=configuration_id,
        )
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
    configuration_id: Annotated[
        str, Path(min_length=1, description="Configuration identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Configurations.ReadWrite"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigurationRecord:
    service = ConfigurationsService(session=session)
    try:
        return await service.activate_configuration(
            workspace_id=workspace.workspace_id,
            configuration_id=configuration_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
