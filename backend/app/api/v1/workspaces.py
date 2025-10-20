from typing import Iterable

from fastapi import APIRouter

from ...schemas.workspaces import Workspace
from ...services import workspaces_service

router = APIRouter()


@router.get("/", response_model=list[Workspace])
async def list_workspaces() -> Iterable[Workspace]:
    return list(workspaces_service.list_workspaces())
