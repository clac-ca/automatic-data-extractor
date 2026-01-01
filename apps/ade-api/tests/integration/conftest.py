from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
import os
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.core.auth.pipeline import reset_auth_state
from ade_api.core.security.hashing import hash_password
from ade_api.db import DatabaseConfig, db
from ade_api.db.migrations import run_migrations_async
from ade_api.features.rbac.service import RbacService
from ade_api.main import create_app
from ade_api.models import Role, User, Workspace, WorkspaceMembership
from ade_api.settings import Settings, get_settings


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


@pytest.fixture(scope="session")
def base_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    root = tmp_path_factory.mktemp("ade-api-tests")
    data_dir = root / "data"

    database_path = data_dir / "db" / "api.sqlite"
    workspaces_dir = data_dir / "workspaces"

    os.environ["ADE_DATABASE_URL"] = f"sqlite:///{database_path}"

    settings = Settings(
        workspaces_dir=workspaces_dir,
        documents_dir=workspaces_dir,
        configs_dir=workspaces_dir,
        runs_dir=workspaces_dir,
        venvs_dir=data_dir / "venvs",
        pip_cache_dir=data_dir / "cache" / "pip",
        auth_disabled=False,
        safe_mode=False,
        jwt_secret="test-jwt-secret-for-tests-please-change",
        oidc_enabled=False,
        oidc_client_id=None,
        oidc_client_secret=None,
        oidc_issuer=None,
        oidc_redirect_url=None,
        auth_force_sso=False,
    )
    ensure_runtime_dirs(settings)
    return settings


@pytest.fixture()
def settings(base_settings: Settings) -> Settings:
    return base_settings.model_copy(deep=True)


@pytest.fixture(scope="session", autouse=True)
def _fast_hash_env() -> Iterator[None]:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ADE_TEST_FAST_HASH", "1")
    yield
    monkeypatch.undo()


@pytest.fixture(autouse=True)
def _reset_auth_caches() -> None:
    reset_auth_state()


@pytest_asyncio.fixture(autouse=True)
async def _override_sessionmaker(
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[None]:
    """Bind background sessions to the test transaction connection."""

    session_factory = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    monkeypatch.setattr(db, "_sessionmaker", session_factory)

    yield


@pytest.fixture(autouse=True)
def _disable_run_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid long-running worker tasks during integration tests."""

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    from ade_api.features.builds.service import BuildsService
    from ade_api.features.runs.worker_pool import RunWorkerPool

    monkeypatch.setattr(BuildsService, "launch_build_if_needed", _noop)
    monkeypatch.setattr(RunWorkerPool, "start", _noop)
    monkeypatch.setattr(RunWorkerPool, "stop", _noop)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def migrated_db(base_settings: Settings) -> AsyncEngine:
    _ = base_settings
    db_config = DatabaseConfig.from_env()
    await run_migrations_async(db_config)
    db.init(db_config)
    engine = db.engine

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        service = RbacService(session=session)
        await service.sync_registry()
        await session.commit()

    yield engine
    await db.dispose()


@pytest_asyncio.fixture()
async def db_connection(migrated_db: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with migrated_db.connect() as connection:
        transaction = await connection.begin()
        if connection.dialect.name == "sqlite":
            await connection.exec_driver_sql("BEGIN")
        try:
            yield connection
        finally:
            if transaction.is_active:
                await transaction.rollback()
            else:
                raise RuntimeError("Test DB transaction was committed; isolation broken.")


@pytest_asyncio.fixture()
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        await session.close()


@pytest.fixture()
def session(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest.fixture()
def app(
    settings: Settings,
    db_connection: AsyncConnection,
) -> FastAPI:
    app = create_app(settings=settings)

    app.dependency_overrides[get_settings] = lambda: cast(Settings, app.state.settings)
    _ = db_connection

    return app


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture()
def override_app_settings(app: FastAPI) -> Callable[..., Settings]:
    def _apply(**updates: Any) -> Settings:
        current = cast(Settings, app.state.settings)
        updated = current.model_copy(update=updates)
        app.state.settings = updated
        app.state.safe_mode = bool(updated.safe_mode)
        ensure_runtime_dirs(updated)
        return updated

    return _apply


@pytest_asyncio.fixture()
async def seed_identity(db_session: AsyncSession) -> SeededIdentity:
    """Create baseline users and workspace records for auth/RBAC tests."""

    rbac_service = RbacService(session=db_session)

    workspace_slug = f"acme-{uuid4().hex[:8]}"
    workspace = Workspace(name="Acme Corp", slug=workspace_slug)
    secondary_workspace = Workspace(name="Globex Corp", slug=f"{workspace_slug}-alt")

    admin_password = "admin-password"
    workspace_owner_password = "workspace-owner-password"
    member_password = "member-password"
    member_manage_password = "member-manage-password"
    orphan_password = "orphan-password"

    admin_email = f"admin+{workspace_slug}@example.com"
    workspace_owner_email = f"owner+{workspace_slug}@example.com"
    member_email = f"member+{workspace_slug}@example.com"
    member_manage_email = f"member-manage+{workspace_slug}@example.com"
    orphan_email = f"orphan+{workspace_slug}@example.com"

    admin = User(
        email=admin_email,
        hashed_password=hash_password(admin_password),
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )
    workspace_owner = User(
        email=workspace_owner_email,
        hashed_password=hash_password(workspace_owner_password),
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )
    member = User(
        email=member_email,
        hashed_password=hash_password(member_password),
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )
    member_with_manage = User(
        email=member_manage_email,
        hashed_password=hash_password(member_manage_password),
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )
    orphan = User(
        email=orphan_email,
        hashed_password=hash_password(orphan_password),
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )

    db_session.add_all(
        [
            workspace,
            secondary_workspace,
            admin,
            workspace_owner,
            member,
            member_with_manage,
            orphan,
        ]
    )
    await db_session.flush()

    admin_role = await rbac_service.get_role_by_slug(slug="global-admin")
    if admin_role is not None:
        await rbac_service.assign_role_if_missing(
            user_id=cast(UUID, admin.id),
            role_id=admin_role.id,
            workspace_id=None,
        )

    member_role = await rbac_service.get_role_by_slug(slug="global-user")
    if member_role is not None:
        for candidate in (
            workspace_owner,
            member,
            member_with_manage,
            orphan,
        ):
            await rbac_service.assign_role_if_missing(
                user_id=cast(UUID, candidate.id),
                role_id=member_role.id,
                workspace_id=None,
            )

    workspace_owner_membership = WorkspaceMembership(
        user_id=workspace_owner.id,
        workspace_id=workspace.id,
        is_default=True,
    )
    member_membership = WorkspaceMembership(
        user_id=member.id,
        workspace_id=workspace.id,
        is_default=True,
    )
    member_manage_default = WorkspaceMembership(
        user_id=member_with_manage.id,
        workspace_id=workspace.id,
        is_default=True,
    )
    member_manage_secondary = WorkspaceMembership(
        user_id=member_with_manage.id,
        workspace_id=secondary_workspace.id,
        is_default=False,
    )

    db_session.add_all(
        [
            workspace_owner_membership,
            member_membership,
            member_manage_default,
            member_manage_secondary,
        ]
    )
    await db_session.flush()

    workspace_roles: dict[str, Role] = {}
    for slug in ("workspace-owner", "workspace-member"):
        role = await rbac_service.get_role_by_slug(slug=slug)
        if role is not None:
            workspace_roles[slug] = role

    async def _assign_workspace_role(
        membership: WorkspaceMembership, user: User, slug: str
    ) -> None:
        role = workspace_roles.get(slug)
        if role is None:
            return
        await rbac_service.assign_role_if_missing(
            user_id=cast(UUID, user.id),
            role_id=role.id,
            workspace_id=cast(UUID, membership.workspace_id),
        )

    await _assign_workspace_role(workspace_owner_membership, workspace_owner, "workspace-owner")
    await _assign_workspace_role(member_membership, member, "workspace-member")
    await _assign_workspace_role(member_manage_default, member_with_manage, "workspace-member")
    await _assign_workspace_role(member_manage_secondary, member_with_manage, "workspace-member")

    owner_role = workspace_roles.get("workspace-owner")
    if owner_role is not None:
        await rbac_service.assign_role_if_missing(
            user_id=cast(UUID, admin.id),
            role_id=owner_role.id,
            workspace_id=cast(UUID, workspace.id),
        )

    await db_session.commit()

    return SeededIdentity(
        workspace_id=cast(UUID, workspace.id),
        secondary_workspace_id=cast(UUID, secondary_workspace.id),
        admin=SeededUser(id=cast(UUID, admin.id), email=admin_email, password=admin_password),
        workspace_owner=SeededUser(
            id=cast(UUID, workspace_owner.id),
            email=workspace_owner_email,
            password=workspace_owner_password,
        ),
        member=SeededUser(id=cast(UUID, member.id), email=member_email, password=member_password),
        member_with_manage=SeededUser(
            id=cast(UUID, member_with_manage.id),
            email=member_manage_email,
            password=member_manage_password,
        ),
        orphan=SeededUser(id=cast(UUID, orphan.id), email=orphan_email, password=orphan_password),
    )
