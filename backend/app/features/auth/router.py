from fastapi import APIRouter

from .schemas import LoginRequest, LoginResponse
from .service import login as login_service
from .service import logout as logout_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    return login_service(payload)


@router.post("/logout", response_model=LoginResponse)
async def logout() -> LoginResponse:
    return logout_service()
