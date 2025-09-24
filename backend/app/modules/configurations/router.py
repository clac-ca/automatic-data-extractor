"""FastAPI routes for configuration metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..events.dependencies import get_events_service
from ..events.schemas import EventRecord
from ..events.service import EventsService
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_configurations_service
from .exceptions import ConfigurationNotFoundError
from .schemas import ConfigurationRecord
from .service import ConfigurationsService


router = APIRouter(tags=["configurations"])


@cbv(router)
class ConfigurationsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: ConfigurationsService = Depends(get_configurations_service)
    events_service: EventsService = Depends(get_events_service)

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
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        document_type: str | None = Query(None),
    ) -> list[ConfigurationRecord]:
        return await self.service.list_configurations(
            limit=limit,
            offset=offset,
            document_type=document_type,
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

    @router.get(
        "/configurations/{configuration_id}/events",
        response_model=list[EventRecord],
        status_code=status.HTTP_200_OK,
        summary="List events recorded for a configuration",
        response_model_exclude_none=True,
    )
    @access_control(
        permissions={"workspace:configurations:read"},
        require_workspace=True,
    )
    async def list_configuration_events(
        self,
        configuration_id: str,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> list[EventRecord]:
        try:
            await self.service.get_configuration(
                configuration_id=configuration_id,
                emit_event=False,
            )
        except ConfigurationNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        return await self.events_service.list_configuration_events(
            configuration_id=configuration_id,
            limit=limit,
            offset=offset,
        )


__all__ = ["router"]
