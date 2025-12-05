"""HTTP routes for listing available configuration templates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security

from ade_api.app.dependencies import get_config_templates_service
from ade_api.core.http import require_authenticated

from .schemas import ConfigTemplate
from .service import ConfigTemplatesService

router = APIRouter(
    prefix="/config-templates",
    tags=["configurations"],
    dependencies=[Security(require_authenticated)],
)


@router.get(
    "",
    response_model=list[ConfigTemplate],
    response_model_exclude_none=True,
    summary="List configuration templates",
)
async def list_config_templates(
    service: Annotated[ConfigTemplatesService, Depends(get_config_templates_service)],
) -> list[ConfigTemplate]:
    return await service.list_templates()


__all__ = ["router"]
