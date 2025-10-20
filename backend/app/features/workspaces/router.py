from typing import Iterable

from fastapi import APIRouter

from .schemas import Workspace
from .service import list_workspaces as list_workspaces_service

router = APIRouter()


@router.get("/", response_model=list[Workspace])
async def list_workspaces() -> Iterable[Workspace]:
    return list(list_workspaces_service())
