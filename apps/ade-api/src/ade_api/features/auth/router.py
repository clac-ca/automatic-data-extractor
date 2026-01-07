"""HTTP interface for authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.routing import APIRoute
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.api.deps import get_auth_service
from ade_api.core.auth.users import (
    UserCreate,
    UserRead,
    build_user_router_factory,
    get_password_helper,
)
from ade_api.core.http import require_csrf
from ade_api.core.http.csrf import set_csrf_cookie
from ade_api.db import get_db_session
from ade_api.models import AccessToken
from ade_api.settings import Settings

from .oidc_router import router as oidc_router
from .schemas import AuthProviderListResponse, AuthSetupRequest, AuthSetupStatusResponse
from .service import AuthService, SetupAlreadyCompletedError


def _add_csrf_logout_dependency(auth_router: APIRouter) -> None:
    for route in auth_router.routes:
        if isinstance(route, APIRoute) and route.path.endswith("/logout"):
            route.dependencies.append(Depends(require_csrf))

async def _require_open_registration(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    status_payload = await service.get_setup_status()
    if status_payload.registration_mode != "open":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

def create_auth_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["auth"])

    fastapi_users, cookie_backend, jwt_backend = build_user_router_factory(settings)

    cookie_router = fastapi_users.get_auth_router(cookie_backend)
    jwt_router = fastapi_users.get_auth_router(jwt_backend)
    _add_csrf_logout_dependency(cookie_router)
    _add_csrf_logout_dependency(jwt_router)

    router.include_router(cookie_router, prefix="/cookie", tags=["auth"])
    router.include_router(jwt_router, prefix="/jwt", tags=["auth"])
    router.include_router(oidc_router, prefix="", tags=["auth"])

    router.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="",
        tags=["auth"],
        dependencies=[Depends(_require_open_registration)],
    )

    @router.get(
        "/setup",
        response_model=AuthSetupStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Return setup status for the first admin user",
    )
    async def get_setup_status(
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> AuthSetupStatusResponse:
        return await service.get_setup_status()

    @router.post(
        "/setup",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Create the first admin user and log them in",
    )
    async def complete_setup(
        payload: AuthSetupRequest,
        service: Annotated[AuthService, Depends(get_auth_service)],
        db: Annotated[AsyncSession, Depends(get_db_session)],
        password_helper: Annotated[PasswordHelper, Depends(get_password_helper)],
    ) -> Response:
        password_hash = password_helper.hash(payload.password.get_secret_value())

        try:
            user = await service.create_first_admin(payload, password_hash=password_hash)
        except SetupAlreadyCompletedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        access_token_db = SQLAlchemyAccessTokenDatabase(db, AccessToken)
        strategy = DatabaseStrategy(
            access_token_db,
            lifetime_seconds=int(settings.session_access_ttl.total_seconds()),
        )
        response = await cookie_backend.login(strategy, user)
        response.status_code = status.HTTP_204_NO_CONTENT
        set_csrf_cookie(response, settings)
        return response

    @router.get(
        "/providers",
        response_model=AuthProviderListResponse,
        status_code=status.HTTP_200_OK,
        summary="Return configured authentication providers",
    )
    async def list_auth_providers(
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> AuthProviderListResponse:
        return service.list_auth_providers()

    return router


__all__ = ["create_auth_router"]
