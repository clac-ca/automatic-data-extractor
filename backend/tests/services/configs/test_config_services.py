"""Unit tests for the configuration services."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.shared.db import generate_ulid
from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.configs.exceptions import DraftFileConflictError, ManifestValidationError
from backend.app.features.configs.models import ConfigVersion
from backend.app.features.configs.schemas import ManifestPatchRequest
from backend.app.features.configs.service import (
    ConfigFileService,
    ConfigService,
    ManifestService,
)
from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace


pytestmark = pytest.mark.asyncio


async def _seed_workspace(session, slug: str | None = None) -> Workspace:
    workspace = Workspace(
        name="Test Workspace",
        slug=slug or f"workspace-{uuid4().hex[:8]}",
    )
    session.add(workspace)
    await session.flush()
    return workspace


async def _seed_user(session, email: str | None = None) -> User:
    user = User(
        id=generate_ulid(),
        email=email or f"user-{uuid4().hex[:6]}@example.test",
        display_name="Config Author",
    )
    session.add(user)
    await session.flush()
    return user


async def test_create_config_initialises_draft() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)

        service = ConfigService(session=session)
        record = await service.create_config(
            workspace_id=str(workspace.id),
            slug="initial-config",
            title="Initial Config",
            actor_id=str(user.id),
        )

        assert record.config_id
        assert record.slug == "initial-config"
        assert record.draft is not None
        assert record.draft.status == "draft"
        assert record.draft.manifest["files_hash"] == ""

        configs = await service.list_configs(workspace_id=str(workspace.id))
        assert len(configs) == 1
        assert configs[0].config_id == record.config_id


async def test_draft_file_updates_recompute_hash() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        config_service = ConfigService(session=session)
        config = await config_service.create_config(
            workspace_id=str(workspace.id),
            slug="hash-check",
            title="Hash Check",
            actor_id=str(user.id),
        )

        file_service = ConfigFileService(session=session)

        created = await file_service.create_draft_file(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            path="columns/postal_code.py",
            code="def transform(value):\n    return value.strip()\n",
            language="python",
        )

        assert created.sha256

        with pytest.raises(DraftFileConflictError):
            await file_service.update_draft_file(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                path="columns/postal_code.py",
                code="# comment\n",
                expected_sha="mismatch",
            )

        updated = await file_service.update_draft_file(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            path="columns/postal_code.py",
            code="def transform(value):\n    return value.lower()\n",
            expected_sha=created.sha256,
        )

        assert updated.sha256 != created.sha256

        refreshed = await config_service.get_config(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
        )
        assert refreshed.draft is not None
        assert refreshed.draft.files_hash
        assert refreshed.draft.files_hash != created.sha256
        assert refreshed.draft.manifest["files_hash"] == refreshed.draft.files_hash


async def test_publish_draft_copies_files() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        config_service = ConfigService(session=session)
        config = await config_service.create_config(
            workspace_id=str(workspace.id),
            slug="publish-flow",
            title="Publish Flow",
            actor_id=str(user.id),
        )

        file_service = ConfigFileService(session=session)
        created = await file_service.create_draft_file(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            path="columns/postal_code.py",
            code="def detect(value):\n    return value\n",
            language="python",
        )

        manifest_service = ManifestService(session=session)
        await manifest_service.patch_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ManifestPatchRequest(
                manifest={
                    "columns": [
                        {
                            "key": "postal_code",
                            "label": "Postal Code",
                            "path": "columns/postal_code.py",
                            "ordinal": 1,
                            "required": True,
                            "enabled": True,
                            "depends_on": [],
                        }
                    ],
                }
            ),
        )

        draft_snapshot = await config_service.get_config(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
        )
        assert draft_snapshot.draft is not None
        draft_hash = draft_snapshot.draft.files_hash

        published = await config_service.publish_draft(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            semver="1.0.0",
            message="Initial release",
            actor_id=str(user.id),
        )

        assert published.status == "published"
        assert published.files_hash == draft_hash

        versions = await config_service.list_versions(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
        )
        statuses = {version.status for version in versions}
        assert statuses == {"draft", "published"}

        result = await session.execute(
            select(ConfigVersion)
            .where(
                ConfigVersion.config_id == config.config_id,
                ConfigVersion.status == "published",
            )
            .limit(1)
        )
        stored = result.scalar_one()
        assert stored.semver == "1.0.0"
        assert stored.files_hash == draft_hash


async def test_publish_draft_with_missing_file_raises() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        config_service = ConfigService(session=session)
        config = await config_service.create_config(
            workspace_id=str(workspace.id),
            slug="publish-invalid",
            title="Publish Invalid",
            actor_id=str(user.id),
        )

        file_service = ConfigFileService(session=session)
        await file_service.create_draft_file(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            path="columns/value.py",
            code="def transform(value):\n    return value\n",
            language="python",
        )

        manifest_service = ManifestService(session=session)
        await manifest_service.patch_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ManifestPatchRequest(
                manifest={
                    "columns": [
                        {
                            "key": "value",
                            "label": "Value",
                            "path": "columns/value.py",
                            "ordinal": 1,
                            "required": True,
                            "enabled": True,
                            "depends_on": [],
                        }
                    ]
                }
            ),
        )

        await file_service.delete_draft_file(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            path="columns/value.py",
        )

        with pytest.raises(ManifestValidationError):
            await config_service.publish_draft(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                semver="1.0.0",
                message="Invalid",
                actor_id=str(user.id),
            )


async def test_manifest_patch_rejects_missing_file() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        config_service = ConfigService(session=session)
        config = await config_service.create_config(
            workspace_id=str(workspace.id),
            slug="manifest-guard",
            title="Manifest Guard",
            actor_id=str(user.id),
        )

        manifest_service = ManifestService(session=session)

        with pytest.raises(ManifestValidationError):
            await manifest_service.patch_manifest(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                payload=ManifestPatchRequest(
                    manifest={
                        "columns": [
                            {
                                "key": "missing",
                                "label": "Missing",
                                "path": "columns/missing.py",
                                "ordinal": 1,
                                "required": True,
                                "enabled": True,
                                "depends_on": [],
                            }
                        ]
                    }
                ),
            )
