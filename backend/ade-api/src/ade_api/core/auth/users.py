"""FastAPI-Users wiring for ADE auth."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
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
from fastapi_users.authentication.strategy.db import AccessTokenDatabase
from fastapi_users.db import BaseUserDatabase
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import Response

from ade_api.db import get_sessionmaker
from ade_db.models import AccessToken, OAuthAccount, User
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
        user_db: BaseUserDatabase[User, UUID],
        settings: Settings,
        password_helper: PasswordHelper,
    ) -> None:
        super().__init__(user_db)
        self.reset_password_token_secret = settings.secret_key_value
        self.verification_token_secret = settings.secret_key_value
        self.password_helper = password_helper

    async def authenticate(self, credentials):  # type: ignore[override]
        user = await super().authenticate(credentials)
        if user is None:
            return None
        if getattr(user, "is_service_account", False):
            return None
        return user


class SyncUserDatabase(BaseUserDatabase[User, UUID]):
    """Async adapter around sync SQLAlchemy sessions for fastapi-users."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        user_table: type[User],
        oauth_account_table: type[OAuthAccount] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.user_table = user_table
        self.oauth_account_table = oauth_account_table

    def _fetch_one(self, statement) -> User | None:
        with self._session_factory() as session:
            result = session.execute(statement)
            return result.unique().scalar_one_or_none()

    async def get(self, id: UUID) -> User | None:
        statement = select(self.user_table).where(self.user_table.id == id)
        return await run_in_threadpool(self._fetch_one, statement)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(self.user_table).where(
            func.lower(self.user_table.email) == func.lower(email)
        )
        return await run_in_threadpool(self._fetch_one, statement)

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> User | None:
        if self.oauth_account_table is None:
            raise NotImplementedError

        statement = (
            select(self.user_table)
            .join(self.oauth_account_table)
            .where(self.oauth_account_table.oauth_name == oauth)  # type: ignore
            .where(self.oauth_account_table.account_id == account_id)  # type: ignore
        )
        return await run_in_threadpool(self._fetch_one, statement)

    async def create(self, create_dict: dict[str, object]) -> User:
        def _create() -> User:
            with self._session_factory() as session:
                user = self.user_table(**create_dict)
                session.add(user)
                session.commit()
                session.refresh(user)
                return user

        return await run_in_threadpool(_create)

    async def update(self, user: User, update_dict: dict[str, object]) -> User:
        def _update() -> User:
            with self._session_factory() as session:
                db_user = session.merge(user)
                for key, value in update_dict.items():
                    setattr(db_user, key, value)
                session.add(db_user)
                session.commit()
                session.refresh(db_user)
                return db_user

        return await run_in_threadpool(_update)

    async def delete(self, user: User) -> None:
        def _delete() -> None:
            with self._session_factory() as session:
                db_user = session.merge(user)
                session.delete(db_user)
                session.commit()

        await run_in_threadpool(_delete)

    async def add_oauth_account(self, user: User, create_dict: dict[str, object]) -> User:
        if self.oauth_account_table is None:
            raise NotImplementedError

        def _add() -> User:
            with self._session_factory() as session:
                db_user = session.merge(user)
                session.refresh(db_user)
                oauth_account = self.oauth_account_table(**create_dict)
                db_user.oauth_accounts.append(oauth_account)  # type: ignore
                session.add(db_user)
                session.commit()
                session.refresh(db_user)
                return db_user

        return await run_in_threadpool(_add)

    async def update_oauth_account(
        self,
        user: User,
        oauth_account: OAuthAccount,
        update_dict: dict[str, object],
    ) -> User:
        if self.oauth_account_table is None:
            raise NotImplementedError

        def _update() -> User:
            with self._session_factory() as session:
                db_user = session.merge(user)
                db_account = session.merge(oauth_account)
                for key, value in update_dict.items():
                    setattr(db_account, key, value)
                session.add(db_account)
                session.commit()
                session.refresh(db_user)
                return db_user

        return await run_in_threadpool(_update)


class SyncAccessTokenDatabase(AccessTokenDatabase[AccessToken]):
    """Async adapter around sync SQLAlchemy sessions for access tokens."""

    def __init__(self, session_factory: sessionmaker[Session], access_token_table: type[AccessToken]):
        self._session_factory = session_factory
        self.access_token_table = access_token_table

    async def get_by_token(
        self, token: str, max_age: datetime | None = None  # type: ignore[name-defined]
    ) -> AccessToken | None:
        def _fetch() -> AccessToken | None:
            stmt = select(self.access_token_table).where(
                self.access_token_table.token == token  # type: ignore
            )
            if max_age is not None:
                stmt = stmt.where(self.access_token_table.created_at >= max_age)  # type: ignore
            with self._session_factory() as session:
                result = session.execute(stmt)
                return result.scalar_one_or_none()

        return await run_in_threadpool(_fetch)

    async def create(self, create_dict: dict[str, object]) -> AccessToken:
        def _create() -> AccessToken:
            with self._session_factory() as session:
                access_token = self.access_token_table(**create_dict)
                session.add(access_token)
                session.commit()
                session.refresh(access_token)
                return access_token

        return await run_in_threadpool(_create)

    async def update(
        self, access_token: AccessToken, update_dict: dict[str, object]
    ) -> AccessToken:
        def _update() -> AccessToken:
            with self._session_factory() as session:
                db_token = session.merge(access_token)
                for key, value in update_dict.items():
                    setattr(db_token, key, value)
                session.add(db_token)
                session.commit()
                session.refresh(db_token)
                return db_token

        return await run_in_threadpool(_update)

    async def delete(self, access_token: AccessToken) -> None:
        def _delete() -> None:
            with self._session_factory() as session:
                db_token = session.merge(access_token)
                session.delete(db_token)
                session.commit()

        await run_in_threadpool(_delete)


async def get_user_db(
    session_factory: Annotated[sessionmaker[Session], Depends(get_sessionmaker)],
) -> AsyncIterator[SyncUserDatabase]:
    yield SyncUserDatabase(session_factory, User, OAuthAccount)


async def get_access_token_db(
    session_factory: Annotated[sessionmaker[Session], Depends(get_sessionmaker)],
) -> AsyncIterator[SyncAccessTokenDatabase]:
    yield SyncAccessTokenDatabase(session_factory, AccessToken)


async def get_user_manager(
    user_db: Annotated[BaseUserDatabase[User, UUID], Depends(get_user_db)],
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
    access_token_db: Annotated[AccessTokenDatabase[AccessToken], Depends(get_access_token_db)],
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
        secret=settings.secret_key_value,
        lifetime_seconds=int(settings.access_token_expire_minutes * 60),
        algorithm=settings.algorithm,
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
