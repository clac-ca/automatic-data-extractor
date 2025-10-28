"""Unit tests for the configuration service (new activation model)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.features.configs.exceptions import (
    ConfigDependentJobsError,
    ConfigInvariantViolationError,
    ConfigVersionActivationError,
    ConfigVersionDependentJobsError,
    VersionFileConflictError,
)
from backend.app.features.configs.models import ConfigVersion
from backend.app.features.configs.schemas import (
    ConfigScriptCreateRequest,
    ConfigScriptUpdateRequest,
    ConfigVersionCreateRequest,
    ManifestPatchRequest,
)
from backend.app.features.configs.service import ConfigService
from backend.app.features.documents.models import Document
from backend.app.features.jobs.models import Job
from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace
from backend.app.shared.db import generate_ulid
from backend.app.shared.db.session import get_sessionmaker


pytestmark = pytest.mark.asyncio


async def _seed_workspace(session) -> Workspace:
    workspace = Workspace(
        name="Test Workspace",
        slug=f"workspace-{uuid4().hex[:8]}",
    )
    session.add(workspace)
    await session.flush()
    return workspace


async def _seed_user(session) -> User:
    user = User(
        id=generate_ulid(),
        email=f"user-{uuid4().hex[:6]}@example.test",
        display_name="Config Author",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_active_version(
    service: ConfigService,
    *,
    workspace_id: str,
    config_id: str,
    semver: str,
    actor_id: str,
) -> str:
    version = await service.create_version(
        workspace_id=workspace_id,
        config_id=config_id,
        payload=ConfigVersionCreateRequest(semver=semver, seed_defaults=True),
        actor_id=actor_id,
    )
    await service.create_script(
        workspace_id=workspace_id,
        config_id=config_id,
        config_version_id=version.config_version_id,
        payload=ConfigScriptCreateRequest(
            path="columns/value.py",
            template="def transform(value):\n    return value\n",
            language="python",
        ),
    )
    manifest, etag = await service.get_manifest(
        workspace_id=workspace_id,
        config_id=config_id,
        config_version_id=version.config_version_id,
    )
    manifest.manifest.setdefault("columns", []).append(
        {
            "key": "value",
            "label": "Value",
            "path": "columns/value.py",
            "ordinal": 1,
            "required": True,
            "enabled": True,
            "depends_on": [],
        }
    )
    await service.update_manifest(
        workspace_id=workspace_id,
        config_id=config_id,
        config_version_id=version.config_version_id,
        payload=ManifestPatchRequest(manifest=manifest.manifest),
        expected_etag=etag,
    )
    await service.activate_version(
        workspace_id=workspace_id,
        config_id=config_id,
        config_version_id=version.config_version_id,
        actor_id=actor_id,
    )
    return version.config_version_id


async def test_create_config_initialises_active_version() -> None:
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

        assert record.active_version is not None
        assert record.active_version.status == "active"
        assert record.versions_count == 1


async def test_create_version_and_activate_replaces_active() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="multi-version",
            title="Multi Version",
            actor_id=str(user.id),
        )

        new_version = await service.create_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ConfigVersionCreateRequest(semver="1.0.0", seed_defaults=True),
            actor_id=str(user.id),
        )

        await service.create_script(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=new_version.config_version_id,
            payload=ConfigScriptCreateRequest(
                path="columns/value.py",
                template="def transform(value):\n    return value\n",
                language="python",
            ),
        )
        manifest, etag = await service.get_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=new_version.config_version_id,
        )
        manifest.manifest["columns"].append(
            {
                "key": "value",
                "label": "Value",
                "path": "columns/value.py",
                "ordinal": 1,
                "required": True,
                "enabled": True,
                "depends_on": [],
            }
        )
        await service.update_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=new_version.config_version_id,
            payload=ManifestPatchRequest(manifest=manifest.manifest),
            expected_etag=etag,
        )

        activated = await service.activate_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=new_version.config_version_id,
            actor_id=str(user.id),
        )
        assert activated.status == "active"

        versions = await service.list_versions(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
        )
        statuses = {version.config_version_id: version.status for version in versions}
        assert statuses[new_version.config_version_id] == "active"
        assert any(status == "inactive" for vid, status in statuses.items() if vid != new_version.config_version_id)


async def test_activate_requires_validation_pass() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="validation-guard",
            title="Validation Guard",
            actor_id=str(user.id),
        )

        version = await service.create_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ConfigVersionCreateRequest(semver="broken", seed_defaults=True),
            actor_id=str(user.id),
        )

        manifest, etag = await service.get_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
        )
        manifest.manifest["columns"].append(
            {
                "key": "missing",
                "label": "Missing",
                "path": "columns/missing.py",
                "ordinal": 1,
                "required": True,
                "enabled": True,
                "depends_on": [],
            }
        )
        await service.update_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
            payload=ManifestPatchRequest(manifest=manifest.manifest),
            expected_etag=etag,
        )

        with pytest.raises(ConfigVersionActivationError):
            await service.activate_version(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                config_version_id=version.config_version_id,
                actor_id=str(user.id),
            )


async def test_file_operations_enforce_etag() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="file-etag",
            title="File ETag",
            actor_id=str(user.id),
        )

        version = await service.create_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ConfigVersionCreateRequest(semver="file-work", seed_defaults=True),
            actor_id=str(user.id),
        )

        created = await service.create_script(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
            payload=ConfigScriptCreateRequest(
                path="columns/value.py",
                template="def transform(value):\n    return value\n",
                language="python",
            ),
        )

        with pytest.raises(VersionFileConflictError):
            await service.create_script(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                config_version_id=version.config_version_id,
                payload=ConfigScriptCreateRequest(
                    path="columns/value.py",
                    template="# duplicate",
                    language="python",
                ),
            )

        with pytest.raises(VersionFileConflictError):
            await service.update_script(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                config_version_id=version.config_version_id,
                path="columns/value.py",
                payload=ConfigScriptUpdateRequest(code="# invalid"),
                expected_sha="mismatch",
            )

        updated = await service.update_script(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
            path="columns/value.py",
            payload=ConfigScriptUpdateRequest(code="def transform(value):\n    return value.upper()\n"),
            expected_sha=created.sha256,
        )
        assert updated.sha256 != created.sha256


async def test_manifest_patch_requires_matching_etag() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="manifest-etag",
            title="Manifest ETag",
            actor_id=str(user.id),
        )

        version = await service.create_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ConfigVersionCreateRequest(semver="manifest", seed_defaults=True),
            actor_id=str(user.id),
        )

        manifest, etag = await service.get_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
        )
        manifest.manifest["notes"] = "first"
        await service.update_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
            payload=ManifestPatchRequest(manifest=manifest.manifest),
            expected_etag=etag,
        )

        with pytest.raises(ConfigInvariantViolationError):
            await service.update_manifest(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                config_version_id=version.config_version_id,
                payload=ManifestPatchRequest(manifest={"notes": "second"}),
                expected_etag=etag,
            )


async def test_validate_version_reports_problems() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="validate-version",
            title="Validate Version",
            actor_id=str(user.id),
        )

        version = await service.create_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            payload=ConfigVersionCreateRequest(semver="validate", seed_defaults=True),
            actor_id=str(user.id),
        )

        manifest, etag = await service.get_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
        )
        manifest.manifest["columns"].append(
            {
                "key": "missing",
                "label": "Missing",
                "path": "columns/missing.py",
                "ordinal": 1,
                "required": True,
                "enabled": True,
                "depends_on": [],
            }
        )
        await service.update_manifest(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
            payload=ManifestPatchRequest(manifest=manifest.manifest),
            expected_etag=etag,
        )

        result = await service.validate_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=version.config_version_id,
        )
        assert not result.ready
        assert result.problems


async def test_hard_delete_config_requires_no_jobs() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="config-delete",
            title="Delete Config",
            actor_id=str(user.id),
        )
        active_version_id = await _create_active_version(
            service,
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            semver="1.0.0",
            actor_id=str(user.id),
        )

        document = Document(
            id=generate_ulid(),
            workspace_id=str(workspace.id),
            original_filename="sample.csv",
            content_type="text/csv",
            byte_size=10,
            sha256="a" * 64,
            stored_uri="s3://example/sample.csv",
            attributes={},
            uploaded_by_user_id=str(user.id),
            expires_at=datetime.now(tz=timezone.utc),
        )
        session.add(document)
        await session.flush()

        job = Job(
            id=generate_ulid(),
            workspace_id=str(workspace.id),
            config_version_id=active_version_id,
            status="pending",
            created_by_user_id=str(user.id),
            input_document_id=document.document_id,
            run_key=None,
            metrics={},
            logs=[],
        )
        session.add(job)
        await session.flush()

        await service.archive_config(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            actor_id=str(user.id),
        )

        with pytest.raises(ConfigDependentJobsError):
            await service.hard_delete_config(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
            )

        await session.delete(job)
        await session.flush()

        await service.hard_delete_config(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
        )

        result = await session.execute(
            select(ConfigVersion).where(ConfigVersion.config_id == config.config_id)
        )
        assert not result.scalars().all()


async def test_hard_delete_version_requires_no_jobs() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await _seed_workspace(session)
        user = await _seed_user(session)
        service = ConfigService(session=session)

        config = await service.create_config(
            workspace_id=str(workspace.id),
            slug="version-delete",
            title="Delete Version",
            actor_id=str(user.id),
        )
        original_version_id = config.active_version.config_version_id  # type: ignore[union-attr]
        active_version_id = await _create_active_version(
            service,
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            semver="1.0.0",
            actor_id=str(user.id),
        )

        document = Document(
            id=generate_ulid(),
            workspace_id=str(workspace.id),
            original_filename="sample.csv",
            content_type="text/csv",
            byte_size=10,
            sha256="b" * 64,
            stored_uri="s3://example/sample.csv",
            attributes={},
            uploaded_by_user_id=str(user.id),
            expires_at=datetime.now(tz=timezone.utc),
        )
        session.add(document)
        await session.flush()

        job = Job(
            id=generate_ulid(),
            workspace_id=str(workspace.id),
            config_version_id=active_version_id,
            status="pending",
            created_by_user_id=str(user.id),
            input_document_id=document.document_id,
            run_key=None,
            metrics={},
            logs=[],
        )
        session.add(job)
        await session.flush()

        # Deactivate the target version before archiving it
        await service.activate_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=original_version_id,
            actor_id=str(user.id),
        )
        await service.archive_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=active_version_id,
            actor_id=str(user.id),
        )

        with pytest.raises(ConfigVersionDependentJobsError):
            await service.hard_delete_version(
                workspace_id=str(workspace.id),
                config_id=config.config_id,
                config_version_id=active_version_id,
            )

        await session.delete(job)
        await session.flush()

        await service.hard_delete_version(
            workspace_id=str(workspace.id),
            config_id=config.config_id,
            config_version_id=active_version_id,
        )

        result = await session.execute(
            select(ConfigVersion).where(ConfigVersion.id == active_version_id)
        )
        assert result.scalar_one_or_none() is None
