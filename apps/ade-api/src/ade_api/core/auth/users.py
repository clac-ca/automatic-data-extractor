"""FastAPI-Users wiring for ADE auth."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users.manager import UUIDIDMixin
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from ade_api.db import get_db_session
from ade_api.models import AccessToken, OAuthAccount, User
from ade_api.settings import Settings, get_settings


class UserRead(schemas.BaseUser[UUID]):
    display_name: str | None = None
    is_service_account: bool = False


class UserCreate(schemas.BaseUserCreate):
    display_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    is_service_account: bool | None = None


@dataclass(frozen=True, slots=True)
class CookieSettings:
    secure: bool
    samesite: str


def _resolve_cookie_settings(settings: Settings) -> CookieSettings:
    frontend_url = settings.frontend_url or settings.server_public_url
    try:
        frontend = urlparse(frontend_url)
        server = urlparse(settings.server_public_url)
        cross_origin = (frontend.scheme, frontend.netloc) != (server.scheme, server.netloc)
    except Exception:
        cross_origin = False

    if cross_origin:
        return CookieSettings(secure=True, samesite="none")

    secure = settings.server_public_url.lower().startswith("https://")
    return CookieSettings(secure=secure, samesite="lax")


def get_password_helper() -> PasswordHelper:
    return PasswordHelper()


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[User, UUID],
        settings: Settings,
        password_helper: PasswordHelper,
    ) -> None:
        super().__init__(user_db)
        self.reset_password_token_secret = settings.jwt_secret_value
        self.verification_token_secret = settings.jwt_secret_value
        self.password_helper = password_helper

    async def authenticate(self, credentials):  # type: ignore[override]
        user = await super().authenticate(credentials)
        if user is None:
            return None
        if getattr(user, "is_service_account", False):
            return None
        return user


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[SQLAlchemyUserDatabase[User, UUID]]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


async def get_access_token_db(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[SQLAlchemyAccessTokenDatabase[AccessToken]]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase[User, UUID], Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    password_helper: Annotated[PasswordHelper, Depends(get_password_helper)],
) -> AsyncIterator[UserManager]:
    yield UserManager(user_db, settings=settings, password_helper=password_helper)


class AdeCookieTransport(CookieTransport):
    def __init__(self, *, settings: Settings, **kwargs: object) -> None:
        self._csrf_cookie_name = settings.session_csrf_cookie_name
        self._cookie_domain = settings.session_cookie_domain
        self._cookie_path = settings.session_cookie_path or "/"
        super().__init__(**kwargs)

    async def get_logout_response(self) -> Response:
        response = await super().get_logout_response()
        response.delete_cookie(
            self._csrf_cookie_name,
            path=self._cookie_path,
            domain=self._cookie_domain,
        )
        return response


def get_cookie_transport(settings: Settings) -> CookieTransport:
    cookie = _resolve_cookie_settings(settings)
    return AdeCookieTransport(
        settings=settings,
        cookie_name=settings.session_cookie_name,
        cookie_max_age=int(settings.session_access_ttl.total_seconds()),
        cookie_path=settings.session_cookie_path or "/",
        cookie_domain=settings.session_cookie_domain,
        cookie_secure=cookie.secure,
        cookie_httponly=True,
        cookie_samesite=cookie.samesite,
    )


def get_database_strategy(
    access_token_db: Annotated[
        SQLAlchemyAccessTokenDatabase[AccessToken], Depends(get_access_token_db)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseStrategy:
    return DatabaseStrategy(
        access_token_db,
        lifetime_seconds=int(settings.session_access_ttl.total_seconds()),
    )


def get_cookie_backend(settings: Settings) -> AuthenticationBackend:
    return AuthenticationBackend(
        name="cookie",
        transport=get_cookie_transport(settings),
        get_strategy=get_database_strategy,
    )


def get_jwt_strategy(settings: Settings) -> JWTStrategy:
    return JWTStrategy(
        secret=settings.jwt_secret_value,
        lifetime_seconds=int(settings.jwt_access_ttl.total_seconds()),
        algorithm=settings.jwt_algorithm,
    )


def get_jwt_backend(settings: Settings) -> AuthenticationBackend:
    transport = BearerTransport(tokenUrl="/api/v1/auth/jwt/login")
    return AuthenticationBackend(
        name="jwt",
        transport=transport,
        get_strategy=lambda: get_jwt_strategy(settings),
    )


def build_user_router_factory(
    settings: Settings,
) -> tuple[FastAPIUsers[User, UUID], AuthenticationBackend, AuthenticationBackend]:
    cookie_backend = get_cookie_backend(settings)
    jwt_backend = get_jwt_backend(settings)
    users = FastAPIUsers(get_user_manager, [cookie_backend, jwt_backend])
    return users, cookie_backend, jwt_backend


__all__ = [
    "UserRead",
    "UserCreate",
    "UserUpdate",
    "UserManager",
    "build_user_router_factory",
    "get_password_helper",
    "get_user_manager",
    "get_user_db",
    "get_access_token_db",
    "get_database_strategy",
]
