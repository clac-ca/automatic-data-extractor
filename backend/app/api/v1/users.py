from typing import Iterable

from fastapi import APIRouter

from ...schemas.users import User
from ...services import users_service

router = APIRouter()


@router.get("/", response_model=list[User])
async def list_users() -> Iterable[User]:
    return list(users_service.list_users())
