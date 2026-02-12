from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.core.auth.pipeline import reset_auth_state
from ade_api.core.security.hashing import hash_password
from ade_api.db import get_db_read, get_db_write
from ade_api.features.rbac.service import RbacService
from ade_api.features.sso.oidc import OidcMetadata
from ade_api.main import create_app
from ade_api.settings import Settings, get_settings
from ade_db.engine import build_engine
from ade_db.migrations_runner import run_migrations
from ade_db.models import User, Workspace, WorkspaceMembership
from tests.integration_support import (
    IsolatedTestDatabase,
    create_isolated_test_database,
    drop_isolated_test_database,
    resolve_isolated_test_database,
    test_env,
)


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


def _build_test_settings(
    tmp_path_factory: pytest.TempPathFactory,
    *,
    database_url: str,
) -> Settings:
    root = tmp_path_factory.mktemp("ade-api-tests")
    data_dir = root / "backend" / "data"

    auth_mode = (test_env("DATABASE_AUTH_MODE") or "password").strip().lower()
    blob_container = test_env("BLOB_CONTAINER") or "ade-test"
    blob_connection_string = test_env("BLOB_CONNECTION_STRING")
    blob_account_url = test_env("BLOB_ACCOUNT_URL")
    if not blob_connection_string and not blob_account_url:
        blob_connection_string = "UseDevelopmentStorage=true"
    settings = Settings(
        _env_file=None,
        data_dir=data_dir,
        auth_disabled=False,
        safe_mode=False,
        secret_key="test-secret-key-for-tests-please-change",
        auth_mode="password_only",
        database_url=database_url,
        database_auth_mode=auth_mode,
        database_sslrootcert=test_env("DATABASE_SSLROOTCERT"),
        blob_container=blob_container,
        blob_connection_string=blob_connection_string,
        blob_account_url=blob_account_url,
        blob_versioning_mode="off",
    )
    ensure_runtime_dirs(settings)
    return settings


def _ensure_blob_container(settings: Settings) -> None:
    if not settings.blob_connection_string:
        return
    try:
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import BlobServiceClient
    except ModuleNotFoundError:
        return

    service = BlobServiceClient.from_connection_string(settings.blob_connection_string)
    container = service.get_container_client(settings.blob_container)
    try:
        container.create_container()
    except ResourceExistsError:
        pass


@pytest.fixture(scope="session")
def isolated_test_database() -> Iterator[IsolatedTestDatabase]:
    database = resolve_isolated_test_database(default_prefix="ade_api_test")
    create_isolated_test_database(database)
    try:
        yield database
    finally:
        drop_isolated_test_database(database)


@pytest.fixture(scope="session")
def base_settings(
    tmp_path_factory: pytest.TempPathFactory,
    isolated_test_database: IsolatedTestDatabase,
) -> Settings:
    settings = _build_test_settings(
        tmp_path_factory,
        database_url=isolated_test_database.database_url.render_as_string(hide_password=False),
    )
    _ensure_blob_container(settings)
    return settings


@pytest.fixture(scope="session", autouse=True)
def _migrate_database(base_settings: Settings) -> None:
    run_migrations(base_settings)


@pytest.fixture()
def empty_database_settings(
    tmp_path_factory: pytest.TempPathFactory,
    isolated_test_database: IsolatedTestDatabase,
) -> Settings:
    return _build_test_settings(
        tmp_path_factory,
        database_url=isolated_test_database.database_url.render_as_string(hide_password=False),
    )


@pytest.fixture()
def settings(app: FastAPI, base_settings: Settings) -> Settings:
    # Keep the shared app on a fresh settings object per test.
    current = base_settings.model_copy()
    app.state.settings_ref["value"] = current
    app.state.settings = current
    return current


@pytest.fixture(scope="session", autouse=True)
def _fast_hash_env() -> Iterator[None]:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ADE_TEST_FAST_HASH", "1")
    yield
    monkeypatch.undo()


@pytest.fixture(autouse=True)
def _reset_auth_caches() -> None:
    reset_auth_state()


@pytest.fixture(autouse=True)
def _clear_runtime_settings_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep integration tests deterministic regardless of shell/.env runtime overrides.
    for key in (
        "ADE_SAFE_MODE",
        "ADE_SAFE_MODE_DETAIL",
        "ADE_AUTH_MODE",
        "ADE_AUTH_IDP_PROVISIONING_MODE",
        "ADE_AUTH_PASSWORD_RESET_ENABLED",
        "ADE_AUTH_PASSWORD_MFA_REQUIRED",
        "ADE_AUTH_PASSWORD_MIN_LENGTH",
        "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE",
        "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE",
        "ADE_AUTH_PASSWORD_REQUIRE_NUMBER",
        "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL",
        "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS",
        "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS",
        "ADE_AUTH_SSO_PROVIDERS_JSON",
        "ADE_AUTH_DISABLED",
        "ADE_AUTH_DISABLED_USER_EMAIL",
        "ADE_AUTH_DISABLED_USER_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _stub_sso_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    from ade_api.features.sso import service as sso_service_module

    def _fake_discover_metadata(issuer: str, _client) -> OidcMetadata:
        normalized = issuer.rstrip("/")
        return OidcMetadata(
            issuer=normalized,
            authorization_endpoint=f"{normalized}/oauth2/v1/authorize",
            token_endpoint=f"{normalized}/oauth2/v1/token",
            jwks_uri=f"{normalized}/oauth2/v1/keys",
        )

    monkeypatch.setattr(sso_service_module, "discover_metadata", _fake_discover_metadata)


@pytest.fixture(scope="session")
def migrated_db(base_settings: Settings, _migrate_database: None) -> Iterator[Engine]:
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


@pytest.fixture(scope="session")
def app(base_settings: Settings) -> FastAPI:
    app_settings = base_settings.model_copy()
    app = create_app(settings=app_settings)

    settings_ref = {"value": app_settings}
    app.state.settings_ref = settings_ref
    app.state.settings = settings_ref["value"]
    app.dependency_overrides[get_settings] = lambda: settings_ref["value"]
    app.state.test_db_sessionmaker = None

    def _resolve_sessionmaker():
        sessionmaker_override = getattr(app.state, "test_db_sessionmaker", None)
        if sessionmaker_override is not None:
            return sessionmaker_override
        app_sessionmaker = getattr(app.state, "db_sessionmaker", None)
        if app_sessionmaker is not None:
            return app_sessionmaker
        raise RuntimeError("Database sessionmaker not initialized for integration test app.")

    def _get_db_write_override():
        session = _resolve_sessionmaker()()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def _get_db_read_override():
        session = _resolve_sessionmaker()()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db_write] = _get_db_write_override
    app.dependency_overrides[get_db_read] = _get_db_read_override
    return app


@pytest.fixture()
def _bind_test_db_sessionmaker(app: FastAPI, db_sessionmaker) -> Iterator[None]:
    previous = getattr(app.state, "test_db_sessionmaker", None)
    previous_app_sessionmaker = getattr(app.state, "db_sessionmaker", None)
    app.state.test_db_sessionmaker = db_sessionmaker
    # Some integration helpers resolve app.state.db_sessionmaker directly.
    app.state.db_sessionmaker = db_sessionmaker
    try:
        yield
    finally:
        app.state.test_db_sessionmaker = previous
        app.state.db_sessionmaker = previous_app_sessionmaker


@pytest_asyncio.fixture(scope="session")
async def started_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture()
async def async_client(
    started_app: FastAPI,
    settings: Settings,
    _bind_test_db_sessionmaker,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=started_app),
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
    def _create_user(email: str, password: str) -> SeededUser:
        user = User(
            email=email,
            email_normalized=email.lower(),
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.flush()
        return SeededUser(id=user.id, email=email, password=password)

    suffix = uuid4().hex[:8]
    admin = _create_user(f"admin-{suffix}@example.com", "admin_pass")
    owner = _create_user(f"owner-{suffix}@example.com", "owner_pass")
    member = _create_user(f"member-{suffix}@example.com", "member_pass")
    member_with_manage = _create_user(f"manage-{suffix}@example.com", "manage_pass")
    orphan = _create_user(f"orphan-{suffix}@example.com", "orphan_pass")

    workspace = Workspace(name="Primary Workspace", slug=f"primary-{suffix}")
    secondary_workspace = Workspace(name="Secondary Workspace", slug=f"secondary-{suffix}")
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
    workspace = Workspace(name="Seeded Workspace", slug=f"seeded-{uuid4().hex[:8]}")
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture()
def seeded_user(db_session: Session, seeded_workspace: Workspace) -> SeededUser:
    email = f"seeded-{uuid4().hex[:8]}@example.com"
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
    suffix = uuid4().hex[:8]
    admin = SeededUser(id=uuid4(), email=f"admin-{suffix}@example.com", password="admin")
    user = SeededUser(id=uuid4(), email=f"user-{suffix}@example.com", password="user")

    workspace = Workspace(name="Workspace", slug=f"workspace-{suffix}")
    db_session.add(workspace)
    db_session.flush()

    admin_user = User(
        id=admin.id,
        email=admin.email,
        email_normalized=admin.email,
        hashed_password=hash_password(admin.password),
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
