"""FastAPI routes for configuration metadata."""

from fastapi import Body, Depends, HTTPException, Query, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import DefaultResponse
from app.core.db.session import get_session
from ..auth.security import access_control
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.routing import workspace_scoped_router
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_configurations_service
from .exceptions import ConfigurationNotFoundError
from .schemas import ConfigurationCreate, ConfigurationRecord, ConfigurationUpdate
from .service import ConfigurationsService

router = workspace_scoped_router(tags=["configurations"])

CONFIGURATION_CREATE_BODY = Body(...)
CONFIGURATION_UPDATE_BODY = Body(...)


@cbv(router)
class ConfigurationsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: ConfigurationsService = Depends(get_configurations_service)

    @router.get(
        "/configurations",
        response_model=list[ConfigurationRecord],
        status_code=status.HTTP_200_OK,
        summary="List configurations for the active workspace",
        response_model_exclude_none=True,
    )
    @access_control(
        permissions={"workspace:configurations:read"},
        require_workspace=True,
    )
    async def list_configurations(
        self,
        document_type: str | None = Query(None),
        is_active: bool | None = Query(None),
    ) -> list[ConfigurationRecord]:
        return await self.service.list_configurations(
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
    @access_control(
        permissions={"workspace:configurations:write"},
        require_workspace=True,
    )
    async def create_configuration(
        self, payload: ConfigurationCreate = CONFIGURATION_CREATE_BODY
    ) -> ConfigurationRecord:
        return await self.service.create_configuration(
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
    @access_control(
        permissions={"workspace:configurations:read"},
        require_workspace=True,
    )
    async def list_active_configurations(
        self, document_type: str | None = Query(None)
    ) -> list[ConfigurationRecord]:
        return await self.service.list_active_configurations(
            document_type=document_type
        )

    @router.get(
        "/configurations/{configuration_id}",
        response_model=ConfigurationRecord,
        status_code=status.HTTP_200_OK,
        summary="Retrieve a configuration by identifier",
        response_model_exclude_none=True,
    )
    @access_control(
        permissions={"workspace:configurations:read"},
        require_workspace=True,
    )
    async def read_configuration(self, configuration_id: str) -> ConfigurationRecord:
        try:
            return await self.service.get_configuration(configuration_id=configuration_id)
        except ConfigurationNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.put(
        "/configurations/{configuration_id}",
        response_model=ConfigurationRecord,
        status_code=status.HTTP_200_OK,
        summary="Replace a configuration",
        response_model_exclude_none=True,
    )
    @access_control(
        permissions={"workspace:configurations:write"},
        require_workspace=True,
    )
    async def replace_configuration(
        self,
        configuration_id: str,
        payload: ConfigurationUpdate = CONFIGURATION_UPDATE_BODY,
    ) -> ConfigurationRecord:
        try:
            return await self.service.update_configuration(
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
    @access_control(
        permissions={"workspace:configurations:write"},
        require_workspace=True,
    )
    async def delete_configuration(
        self, configuration_id: str
    ) -> DefaultResponse:
        try:
            await self.service.delete_configuration(configuration_id=configuration_id)
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
    @access_control(
        permissions={"workspace:configurations:write"},
        require_workspace=True,
    )
    async def activate_configuration(
        self, configuration_id: str
    ) -> ConfigurationRecord:
        try:
            return await self.service.activate_configuration(
                configuration_id=configuration_id
            )
        except ConfigurationNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
