"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import Settings, get_settings, reload_settings
from app.db.bootstrap import ensure_database_ready
from app.db.engine import render_sync_url, reset_database_state
from app.db.session import get_sessionmaker
from app.features.auth.security import hash_password
from app.features.users.models import User, UserRole
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)
from app.lifecycles import ensure_runtime_dirs
from app.main import create_app


@pytest.fixture(scope="session")
def _database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Provide a file-backed SQLite database URL for the test session."""

    db_path = tmp_path_factory.mktemp("ade-db") / "ade.sqlite"
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(scope="session", autouse=True)
def _configure_database(
    _database_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[None]:
    """Apply Alembic migrations against the ephemeral test database."""

    data_dir = tmp_path_factory.mktemp("ade-data")
    documents_dir = data_dir / "documents"

    os.environ["ADE_DATABASE_DSN"] = _database_url
    os.environ["ADE_STORAGE_DATA_DIR"] = str(data_dir)
    os.environ["ADE_STORAGE_DOCUMENTS_DIR"] = str(documents_dir)
    settings = reload_settings()
    assert settings.database_dsn == _database_url
    ensure_runtime_dirs(settings)
    reset_database_state()

    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", render_sync_url(_database_url))
    command.upgrade(config, "head")

    yield

    command.downgrade(config, "base")
    reset_database_state()
    reload_settings()
    for env_var in (
        "ADE_DATABASE_DSN",
        "ADE_STORAGE_DATA_DIR",
        "ADE_STORAGE_DOCUMENTS_DIR",
    ):
        os.environ.pop(env_var, None)


@pytest.fixture(scope="session")
def app(_configure_database: None) -> FastAPI:
    """Return an application instance for integration-style tests."""

    return create_app()


@pytest.fixture()
def override_app_settings(app: FastAPI) -> Callable[..., Settings]:
    """Refresh application settings for a test case."""

    original = app.state.settings

    def _apply(**updates: Any) -> Settings:
        base = reload_settings()
        updated = base.model_copy(update=updates)
        app.state.settings = updated
        ensure_runtime_dirs(updated)
        return updated

    yield _apply

    app.state.settings = original
    ensure_runtime_dirs(original)
    reload_settings()


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Provide an HTTPX async client bound to the FastAPI app."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def _reset_task_queue(app: FastAPI) -> AsyncIterator[None]:
    """Ensure the in-memory task queue is empty between tests."""

    queue = getattr(app.state, "task_queue", None)
    if queue is not None:
        await queue.clear()
    yield
    if queue is not None:
        await queue.clear()


@pytest_asyncio.fixture()
async def seed_identity(app: FastAPI) -> dict[str, Any]:
    """Create baseline users and workspace records for identity tests."""

    settings = get_settings()
    await ensure_database_ready(settings)
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        workspace_slug = f"acme-{uuid4().hex[:8]}"
        workspace = Workspace(name="Acme Corp", slug=workspace_slug)
        secondary_workspace = Workspace(
            name="Globex Corp", slug=f"{workspace_slug}-alt"
        )
        admin_password = "admin-password"
        workspace_owner_password = "workspace-owner-password"
        member_password = "member-password"
        member_manage_password = "member-manage-password"
        orphan_password = "orphan-password"
        invitee_password = "invitee-password"

        admin_email = f"admin+{workspace_slug}@example.test"
        workspace_owner_email = f"owner+{workspace_slug}@example.test"
        member_email = f"member+{workspace_slug}@example.test"
        member_manage_email = f"member-manage+{workspace_slug}@example.test"
        orphan_email = f"orphan+{workspace_slug}@example.test"
        invitee_email = f"invitee+{workspace_slug}@example.test"

        admin = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        workspace_owner = User(
            email=workspace_owner_email,
            password_hash=hash_password(workspace_owner_password),
            role=UserRole.MEMBER,
            is_active=True,
        )
        member = User(
            email=member_email,
            password_hash=hash_password(member_password),
            role=UserRole.MEMBER,
            is_active=True,
        )
        member_with_manage = User(
            email=member_manage_email,
            password_hash=hash_password(member_manage_password),
            role=UserRole.MEMBER,
            is_active=True,
        )
        orphan = User(
            email=orphan_email,
            password_hash=hash_password(orphan_password),
            role=UserRole.MEMBER,
            is_active=True,
        )
        invitee = User(
            email=invitee_email,
            password_hash=hash_password(invitee_password),
            role=UserRole.MEMBER,
            is_active=True,
        )

        session.add_all(
            [
                workspace,
                secondary_workspace,
                admin,
                workspace_owner,
                member,
                member_with_manage,
                orphan,
                invitee,
            ]
        )
        await session.flush()

        automation_account = User(
            email=f"automation-{workspace_slug}@service.local",
            display_name="Automation Bot",
            description="Integration user for automation tasks",
            is_service_account=True,
            is_active=True,
            created_by_user_id=admin.id,
        )
        inactive_account = User(
            email=f"inactive-{workspace_slug}@service.local",
            display_name="Inactive Bot",
            description="Disabled integration",
            is_service_account=True,
            is_active=False,
            created_by_user_id=admin.id,
        )
        session.add_all([automation_account, inactive_account])
        await session.flush()

        workspace_owner_membership = WorkspaceMembership(
            user_id=workspace_owner.id,
            workspace_id=workspace.id,
            role=WorkspaceRole.OWNER,
            is_default=True,
            permissions=[],
        )
        member_membership = WorkspaceMembership(
            user_id=member.id,
            workspace_id=workspace.id,
            role=WorkspaceRole.MEMBER,
            is_default=True,
            permissions=["workspace:dashboard:read"],
        )
        member_manage_default = WorkspaceMembership(
            user_id=member_with_manage.id,
            workspace_id=workspace.id,
            role=WorkspaceRole.MEMBER,
            is_default=True,
            permissions=["workspace:members:manage"],
        )
        member_manage_secondary = WorkspaceMembership(
            user_id=member_with_manage.id,
            workspace_id=secondary_workspace.id,
            role=WorkspaceRole.MEMBER,
            is_default=False,
            permissions=[],
        )

        session.add_all(
            [
                workspace_owner_membership,
                member_membership,
                member_manage_default,
                member_manage_secondary,
            ]
        )
        await session.commit()

        workspace_id = workspace.id
        secondary_workspace_id = secondary_workspace.id
        admin_info = {"email": admin_email, "password": admin_password, "id": admin.id}
        workspace_owner_info = {
            "email": workspace_owner_email,
            "password": workspace_owner_password,
            "id": workspace_owner.id,
        }
        member_info = {"email": member_email, "password": member_password, "id": member.id}
        member_manage_info = {
            "email": member_manage_email,
            "password": member_manage_password,
            "id": member_with_manage.id,
        }
        orphan_info = {"email": orphan_email, "password": orphan_password, "id": orphan.id}
        invitee_info = {
            "email": invitee_email,
            "password": invitee_password,
            "id": invitee.id,
        }

    return {
        "workspace_id": workspace_id,
        "secondary_workspace_id": secondary_workspace_id,
        "admin": admin_info,
        "workspace_owner": workspace_owner_info,
        "member": member_info,
        "member_with_manage": member_manage_info,
        "orphan": orphan_info,
        "invitee": invitee_info,
        "service_account": {
            "id": automation_account.id,
            "email": automation_account.email,
            "display_name": automation_account.display_name,
        },
        "inactive_service_account": {
            "id": inactive_account.id,
            "email": inactive_account.email,
            "display_name": inactive_account.display_name,
        },
    }
