from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.core.auth.pipeline import reset_auth_state
from ade_api.core.security.hashing import hash_password
from ade_api.db import build_engine, get_db, get_sessionmaker
from ade_api.db.migrations import run_migrations
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
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url_override=f"sqlite:///{database_path.as_posix()}",
        data_dir=data_dir,
        auth_disabled=False,
        safe_mode=False,
        jwt_secret="test-jwt-secret-for-tests-please-change",
        auth_force_sso=False,
    )
    ensure_runtime_dirs(settings)
    return settings


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


@pytest.fixture(scope="session")
def migrated_db(base_settings: Settings) -> Iterator[Engine]:
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
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
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
    app.dependency_overrides[get_sessionmaker] = lambda: db_sessionmaker

    return app


@pytest_asyncio.fixture()
async def async_client(app: FastAPI, db_sessionmaker) -> AsyncIterator[AsyncClient]:
    async with LifespanManager(app):
        app.state.db_sessionmaker = db_sessionmaker
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest.fixture()
def override_app_settings(app: FastAPI) -> Callable[..., Settings]:
    def _apply(**updates: Any) -> Settings:
        settings_ref = app.state.settings_ref
        current = settings_ref["value"]
        updated = current.model_copy(update=updates)
        settings_ref["value"] = updated
        app.state.settings = updated
        app.state.safe_mode = bool(updated.safe_mode)
        ensure_runtime_dirs(updated)
        return updated

    return _apply


@pytest.fixture()
def seed_identity(db_session: Session) -> SeededIdentity:
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
    db_session.flush()

    admin_role = rbac_service.get_role_by_slug(slug="global-admin")
    if admin_role is not None:
        rbac_service.assign_role_if_missing(
            user_id=cast(UUID, admin.id),
            role_id=admin_role.id,
            workspace_id=None,
        )

    member_role = rbac_service.get_role_by_slug(slug="global-user")
    if member_role is not None:
        for candidate in (
            workspace_owner,
            member,
            member_with_manage,
            orphan,
        ):
            rbac_service.assign_role_if_missing(
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
    db_session.flush()

    workspace_roles: dict[str, Role] = {}
    for slug in ("workspace-owner", "workspace-member"):
        role = rbac_service.get_role_by_slug(slug=slug)
        if role is not None:
            workspace_roles[slug] = role

    def _assign_workspace_role(
        membership: WorkspaceMembership, user: User, slug: str
    ) -> None:
        role = workspace_roles.get(slug)
        if role is None:
            return
        rbac_service.assign_role_if_missing(
            user_id=cast(UUID, user.id),
            role_id=role.id,
            workspace_id=cast(UUID, membership.workspace_id),
        )

    _assign_workspace_role(workspace_owner_membership, workspace_owner, "workspace-owner")
    _assign_workspace_role(member_membership, member, "workspace-member")
    _assign_workspace_role(member_manage_default, member_with_manage, "workspace-member")
    _assign_workspace_role(member_manage_secondary, member_with_manage, "workspace-member")

    owner_role = workspace_roles.get("workspace-owner")
    if owner_role is not None:
        rbac_service.assign_role_if_missing(
            user_id=cast(UUID, admin.id),
            role_id=owner_role.id,
            workspace_id=cast(UUID, workspace.id),
        )

    db_session.commit()

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
