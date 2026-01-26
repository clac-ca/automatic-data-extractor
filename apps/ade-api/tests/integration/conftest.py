from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
import os
import re
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.core.auth.pipeline import reset_auth_state
from ade_api.core.security.hashing import hash_password
from ade_api.db import build_engine, get_db, get_sessionmaker
from ade_api.db.migrations import run_migrations
from ade_api.features.rbac.service import RbacService
from ade_api.main import create_app
from ade_api.models import Role, User, Workspace, WorkspaceMembership
from ade_api.settings import DEFAULT_DATABASE_AUTH_MODE, DEFAULT_DATABASE_URL, Settings, get_settings


@dataclass(frozen=True, slots=True)
class SeededUser:
    id: UUID
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class SeededIdentity:
    workspace_id: UUID
    secondary_workspace_id: UUID
    admin: SeededUser
    workspace_owner: SeededUser
    member: SeededUser
    member_with_manage: SeededUser
    orphan: SeededUser

    @property
    def user(self) -> SeededUser:
        return self.member


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"ADE_TEST_{name}") or os.getenv(f"ADE_{name}") or default


def _sanitize_db_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return sanitized or "ade_test"


def _resolve_test_database_name() -> str:
    explicit = os.getenv("ADE_TEST_DATABASE_NAME")
    if explicit:
        return _sanitize_db_name(explicit)
    prefix = os.getenv("ADE_TEST_DATABASE_NAME_PREFIX") or "ade_test"
    prefix = _sanitize_db_name(prefix)
    suffix = uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def _build_test_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    root = tmp_path_factory.mktemp("ade-api-tests")
    data_dir = root / "data"

    auth_mode = (_env("DATABASE_AUTH_MODE", DEFAULT_DATABASE_AUTH_MODE) or "password").strip().lower()
    base_url = _env("DATABASE_URL", DEFAULT_DATABASE_URL) or DEFAULT_DATABASE_URL
    url = make_url(base_url).set(database=_resolve_test_database_name())
    settings = Settings(
        _env_file=None,
        data_dir=data_dir,
        auth_disabled=False,
        safe_mode=False,
        secret_key="test-secret-key-for-tests-please-change",
        auth_force_sso=False,
        database_url=url.render_as_string(hide_password=False),
        database_auth_mode=auth_mode,
        database_sslrootcert=_env("DATABASE_SSLROOTCERT"),
        blob_require_versioning=False,
        blob_create_container_on_startup=True,
    )
    ensure_runtime_dirs(settings)
    return settings


def _build_admin_settings(settings: Settings) -> Settings:
    url = make_url(settings.database_url).set(database="postgres")
    payload = settings.model_dump()
    payload["database_url"] = url.render_as_string(hide_password=False)
    return Settings.model_validate(payload)


def _create_database(settings: Settings) -> None:
    admin_settings = _build_admin_settings(settings)
    db_name = make_url(settings.database_url).database
    if not db_name:
        raise RuntimeError("Test database name was empty; check ADE_TEST_DATABASE_NAME settings.")
    engine = build_engine(admin_settings)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{db_name}";')
    finally:
        engine.dispose()


def _drop_database(settings: Settings) -> None:
    admin_settings = _build_admin_settings(settings)
    db_name = make_url(settings.database_url).database
    if not db_name:
        return
    engine = build_engine(admin_settings)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                      AND pid <> pg_backend_pid();
                    """
                ),
                {"db_name": db_name},
            )
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}";')
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def base_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    settings = _build_test_settings(tmp_path_factory)
    return settings


@pytest.fixture()
def empty_database_settings(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Settings]:
    settings = _build_test_settings(tmp_path_factory)
    _create_database(settings)
    try:
        yield settings
    finally:
        _drop_database(settings)


@pytest.fixture()
def settings(base_settings: Settings) -> Settings:
    return base_settings.model_copy()


@pytest.fixture(scope="session", autouse=True)
def _fast_hash_env() -> Iterator[None]:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ADE_TEST_FAST_HASH", "1")
    yield
    monkeypatch.undo()


@pytest.fixture(autouse=True)
def _reset_auth_caches() -> None:
    reset_auth_state()


@pytest.fixture(scope="session", autouse=True)
def _database_lifecycle(base_settings: Settings) -> Iterator[None]:
    _create_database(base_settings)
    yield
    _drop_database(base_settings)


@pytest.fixture(scope="session")
def migrated_db(base_settings: Settings, _database_lifecycle: None) -> Iterator[Engine]:
    run_migrations(base_settings)
    engine = build_engine(base_settings)

    with Session(engine) as session:
        service = RbacService(session=session)
        service.sync_registry()
        session.commit()

    yield engine
    engine.dispose()


@pytest.fixture()
def db_connection(migrated_db: Engine) -> Iterator[Connection]:
    with migrated_db.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()
            else:
                raise RuntimeError("Test DB transaction was committed; isolation broken.")


@pytest.fixture()
def db_sessionmaker(db_connection: Connection):
    return sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture()
def db_session(db_sessionmaker) -> Iterator[Session]:
    session = db_sessionmaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(
    settings: Settings,
    db_sessionmaker,
    migrated_db,
) -> FastAPI:
    app = create_app(settings=settings)

    settings_ref = {"value": settings}
    app.state.settings_ref = settings_ref
    app.state.settings = settings_ref["value"]
    app.dependency_overrides[get_settings] = lambda: settings_ref["value"]

    def _get_db_override():
        session = db_sessionmaker()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db_override
    return app


@pytest_asyncio.fixture()
async def async_client(
    app: FastAPI,
    db_sessionmaker,
    migrated_db: Engine,
) -> AsyncIterator[AsyncClient]:
    async with LifespanManager(app):
        app.state.db_sessionmaker = db_sessionmaker
        app.state.db_engine = migrated_db
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.fixture()
def override_app_settings(app: FastAPI) -> Iterator[Callable[..., None]]:
    settings_ref = app.state.settings_ref
    original = settings_ref["value"]

    def _override(**updates: Any) -> None:
        payload = settings_ref["value"].model_dump()
        payload.update(updates)
        settings_ref["value"] = Settings.model_validate(payload)
        app.state.settings = settings_ref["value"]

    try:
        yield _override
    finally:
        settings_ref["value"] = original
        app.state.settings = original


@pytest.fixture()
def seeded_identity(db_session: Session) -> SeededIdentity:
    def _create_user(email: str, password: str, *, is_superuser: bool = False) -> SeededUser:
        user = User(
            email=email,
            email_normalized=email.lower(),
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=True,
            is_superuser=is_superuser,
        )
        db_session.add(user)
        db_session.flush()
        return SeededUser(id=user.id, email=email, password=password)

    admin = _create_user("admin@example.com", "admin_pass", is_superuser=True)
    owner = _create_user("owner@example.com", "owner_pass")
    member = _create_user("member@example.com", "member_pass")
    member_with_manage = _create_user("manage@example.com", "manage_pass")
    orphan = _create_user("orphan@example.com", "orphan_pass")

    workspace = Workspace(name="Primary Workspace", slug="primary")
    secondary_workspace = Workspace(name="Secondary Workspace", slug="secondary")
    db_session.add_all([workspace, secondary_workspace])
    db_session.flush()

    rbac = RbacService(session=db_session)
    rbac.sync_registry()
    admin_role = rbac.get_role_by_slug(slug="global-admin")
    global_user_role = rbac.get_role_by_slug(slug="global-user")
    owner_role = rbac.get_role_by_slug(slug="workspace-owner")
    member_role = rbac.get_role_by_slug(slug="workspace-member")
    if global_user_role is not None:
        for user_id in (admin.id, owner.id, member.id, member_with_manage.id, orphan.id):
            rbac.assign_role_if_missing(
                user_id=user_id,
                role_id=global_user_role.id,
                workspace_id=None,
            )
    if admin_role is not None:
        rbac.assign_role_if_missing(user_id=admin.id, role_id=admin_role.id, workspace_id=None)
    if owner_role is not None:
        rbac.assign_role_if_missing(
            user_id=owner.id,
            role_id=owner_role.id,
            workspace_id=workspace.id,
        )
    if member_role is not None:
        for user_id, workspace_id in (
            (member.id, workspace.id),
            (member_with_manage.id, workspace.id),
            (orphan.id, secondary_workspace.id),
        ):
            rbac.assign_role_if_missing(
                user_id=user_id,
                role_id=member_role.id,
                workspace_id=workspace_id,
            )

    db_session.add(
        WorkspaceMembership(
            user_id=owner.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )
    db_session.add(
        WorkspaceMembership(
            user_id=member.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )
    db_session.add(
        WorkspaceMembership(
            user_id=member_with_manage.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )
    db_session.add(
        WorkspaceMembership(
            user_id=orphan.id,
            workspace_id=secondary_workspace.id,
            is_default=True,
        )
    )

    db_session.commit()

    return SeededIdentity(
        workspace_id=cast(UUID, workspace.id),
        secondary_workspace_id=cast(UUID, secondary_workspace.id),
        admin=admin,
        workspace_owner=owner,
        member=member,
        member_with_manage=member_with_manage,
        orphan=orphan,
    )


@pytest.fixture()
def seed_identity(seeded_identity: SeededIdentity) -> SeededIdentity:
    return seeded_identity


@pytest.fixture()
def seeded_workspace(db_session: Session) -> Workspace:
    workspace = Workspace(name="Seeded Workspace", slug="seeded")
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture()
def seeded_user(db_session: Session, seeded_workspace: Workspace) -> SeededUser:
    email = "seeded@example.com"
    password = "seeded_pass"
    user = User(
        email=email,
        email_normalized=email.lower(),
        hashed_password=hash_password(password),
    )
    db_session.add(user)
    db_session.flush()

    db_session.add(
        WorkspaceMembership(
            user_id=user.id,
            workspace_id=seeded_workspace.id,
            is_default=True,
        )
    )
    db_session.commit()
    return SeededUser(id=user.id, email=email, password=password)


@pytest.fixture()
def seeded_workspace_with_user(db_session: Session) -> SeededIdentity:
    admin = SeededUser(id=uuid4(), email="admin@example.com", password="admin")
    user = SeededUser(id=uuid4(), email="user@example.com", password="user")

    workspace = Workspace(name="Workspace", slug="workspace")
    db_session.add(workspace)
    db_session.flush()

    admin_user = User(
        id=admin.id,
        email=admin.email,
        email_normalized=admin.email,
        hashed_password=hash_password(admin.password),
        is_superuser=True,
    )
    regular_user = User(
        id=user.id,
        email=user.email,
        email_normalized=user.email,
        hashed_password=hash_password(user.password),
    )
    db_session.add_all([admin_user, regular_user])
    db_session.flush()

    db_session.add(
        WorkspaceMembership(
            user_id=admin.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )
    db_session.add(
        WorkspaceMembership(
            user_id=user.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )
    db_session.commit()

    return SeededIdentity(
        workspace_id=cast(UUID, workspace.id),
        secondary_workspace_id=cast(UUID, workspace.id),
        admin=admin,
        workspace_owner=admin,
        member=user,
        member_with_manage=user,
        orphan=user,
    )
