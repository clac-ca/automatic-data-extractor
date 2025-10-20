from fastapi import APIRouter

from ...schemas.auth import LoginRequest, LoginResponse
from ...services import auth_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    return auth_service.login(payload)


@router.post("/logout", response_model=LoginResponse)
async def logout() -> LoginResponse:
    return auth_service.logout()
