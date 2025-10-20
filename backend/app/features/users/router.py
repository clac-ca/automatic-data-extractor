from typing import Iterable

from fastapi import APIRouter

from .schemas import User
from .service import list_users as list_users_service

router = APIRouter()


@router.get("/", response_model=list[User])
async def list_users() -> Iterable[User]:
    return list(list_users_service())
