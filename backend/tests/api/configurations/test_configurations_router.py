"""Configuration router tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import textwrap

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update

from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.configurations.models import Configuration
from backend.tests.utils import login


VALID_SCRIPT = textwrap.dedent(
    '''
    """
    name: sample_column
    description: Example configuration script for tests.
    version: 1
    """

    def detect_sample(
        *, header=None, values=None, table=None, column_index=None, state=None, context=None, **kwargs
    ):
        return {"scores": {"self": 1.0}}

    def transform_cell(
        *, value=None, row_index=None, column_index=None, table=None, state=None, context=None, **kwargs
    ):
        return {"cells": {"self": value}}
    '''
)


pytestmark = pytest.mark.asyncio


async def _create_configuration(*, workspace_id: str, **overrides: Any) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        is_active = overrides.get("is_active", False)
        activated_at = overrides.get("activated_at")
        if activated_at is None and is_active:
            activated_at = datetime.now(UTC).replace(microsecond=0)

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.workspace_id == workspace_id,
            )
        )
        latest = result.scalar_one_or_none() or 0
        version = overrides.get("version", latest + 1)

        configuration = Configuration(
            workspace_id=workspace_id,
            title=overrides.get("title", "Baseline configuration"),
            version=version,
            is_active=is_active,
            activated_at=activated_at,
            payload=overrides.get("payload", {"rules": []}),
        )
        if is_active:
            await session.execute(
                update(Configuration)
                .where(
                    Configuration.workspace_id == workspace_id,
                    Configuration.is_active.is_(True),
                )
                .values(is_active=False, activated_at=None)
            )
        session.add(configuration)
        await session.flush()
        configuration_id = str(configuration.id)
        await session.commit()
    return configuration_id


async def _get_configuration(configuration_id: str) -> Configuration | None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        return await session.get(Configuration, configuration_id)


async def test_list_configurations_supports_filters(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Listing configurations should support status filters."""

    workspace_id = seed_identity["workspace_id"]

    inactive_id = await _create_configuration(
        workspace_id=workspace_id,
        is_active=False,
    )
    active_id = await _create_configuration(
        workspace_id=workspace_id,
        is_active=True,
    )
    await _create_configuration(
        workspace_id=workspace_id,
        is_active=False,
    )

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.get(
        f"{workspace_base}/configurations",
        params={"is_active": "true"},
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    identifiers = {item["configuration_id"] for item in payload}
    assert active_id in identifiers
    assert inactive_id not in identifiers


async def test_create_configuration_assigns_next_version(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Creating a configuration should increment the version counter."""

    workspace_id = seed_identity["workspace_id"]
    baseline_id = await _create_configuration(
        workspace_id=workspace_id,
    )
    baseline = await _get_configuration(baseline_id)
    assert baseline is not None
    baseline_version = baseline.version

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.post(
        f"{workspace_base}/configurations",
        json={
            "title": "Updated rules",
            "payload": {"rules": ["A", "B"]},
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["version"] == baseline_version + 1
    assert payload["is_active"] is False
    assert "document_type" not in payload

    configuration = await _get_configuration(payload["configuration_id"])
    assert configuration is not None
    assert configuration.version == baseline_version + 1


async def test_read_configuration_returns_payload(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Fetching a single configuration should return configuration details."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.get(
        f"{workspace_base}/configurations/{configuration_id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuration_id"] == configuration_id


async def _create_script_version(
    *,
    async_client: AsyncClient,
    workspace_base: str,
    configuration_id: str,
    token: str,
    canonical_key: str = "sample_column",
) -> tuple[str, str]:
    response = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/{canonical_key}/versions",
        json={
            "canonical_key": canonical_key,
            "language": "python",
            "code": VALID_SCRIPT,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    etag = response.headers.get("etag")
    assert etag, "ETag header missing"
    return body["script_version_id"], etag


async def test_read_configuration_not_found_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown configuration identifiers should yield a 404 response."""

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.get(
        f"{workspace_base}/configurations/does-not-exist",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 404


async def test_update_configuration_replaces_fields(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """PUT should replace mutable fields on the configuration."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(
        workspace_id=workspace_id,
        title="Initial",
        payload={"rules": ["A"]},
    )

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}",
        json={
            "title": "Replaced",
            "payload": {"rules": ["B", "C"]},
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "Replaced"
    assert payload["payload"] == {"rules": ["B", "C"]}

    configuration = await _get_configuration(configuration_id)
    assert configuration is not None
    assert configuration.title == "Replaced"
    assert configuration.payload == {"rules": ["B", "C"]}


async def test_delete_configuration_removes_record(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """DELETE should remove the configuration."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.delete(
        f"{workspace_base}/configurations/{configuration_id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Configuration deleted"
    assert await _get_configuration(configuration_id) is None


async def test_activate_configuration_toggles_previous_active(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Activating a configuration should deactivate previous versions."""

    workspace_id = seed_identity["workspace_id"]
    previous_id = await _create_configuration(
        workspace_id=workspace_id,
        is_active=True,
    )
    target_id = await _create_configuration(
        workspace_id=workspace_id,
        is_active=False,
    )

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.post(
        f"{workspace_base}/configurations/{target_id}/activate",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configuration_id"] == target_id
    assert payload["is_active"] is True
    assert payload["activated_at"]

    new_active = await _get_configuration(target_id)
    assert new_active is not None and new_active.is_active is True
    previous = await _get_configuration(previous_id)
    assert previous is not None and previous.is_active is False


async def test_list_active_configurations_returns_current(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Active configurations endpoint should only return the current active version."""

    workspace_id = seed_identity["workspace_id"]
    active_id = await _create_configuration(
        workspace_id=workspace_id,
        is_active=True,
    )
    await _create_configuration(
        workspace_id=workspace_id,
        is_active=False,
    )
    await _create_configuration(
        workspace_id=workspace_id,
        is_active=False,
    )

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.get(
        f"{workspace_base}/configurations/active",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    identifiers = {item["configuration_id"] for item in payload}
    assert identifiers == {active_id}


async def test_replace_columns_round_trip(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """PUT should replace columns and GET should return the stored order."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    response = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}/columns",
        json=[
            {
                "canonical_key": "sample_column",
                "ordinal": 0,
                "display_label": "Sample",
                "header_color": "#ffffff",
                "width": 120,
                "required": True,
                "enabled": True,
                "params": {"threshold": 1},
            },
            {
                "canonical_key": "secondary",
                "ordinal": 1,
                "display_label": "Secondary",
                "required": False,
                "enabled": True,
                "params": {},
            },
        ],
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [column["canonical_key"] for column in payload] == [
        "sample_column",
        "secondary",
    ]

    fetch = await async_client.get(
        f"{workspace_base}/configurations/{configuration_id}/columns",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetch.status_code == 200
    listed = fetch.json()
    assert len(listed) == 2
    assert listed[0]["display_label"] == "Sample"
    assert "script_version" not in listed[0]


async def test_configuration_script_version_lifecycle(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Uploading, listing, fetching, and validating scripts should work."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    script_id, etag = await _create_script_version(
        async_client=async_client,
        workspace_base=workspace_base,
        configuration_id=configuration_id,
        token=token,
    )

    listing = await async_client.get(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    versions = listing.json()
    assert [item["script_version_id"] for item in versions] == [script_id]
    assert "code" not in versions[0]

    fetch = await async_client.get(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions/{script_id}",
        params={"include_code": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetch.status_code == 200
    fetched = fetch.json()
    assert fetched["script_version_id"] == script_id
    assert "name: sample_column" in fetched["code"]

    validate = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions/{script_id}:validate",
        headers={
            "Authorization": f"Bearer {token}",
            "If-Match": etag,
        },
    )
    assert validate.status_code == 200, validate.text
    assert validate.headers.get("etag") == etag
    validated = validate.json()
    assert validated["validated_at"] is not None


async def test_configuration_script_size_limit_is_enforced(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Scripts larger than the size cap should record validation errors."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    oversized_payload = "x" * 40000
    script = textwrap.dedent(
        f'''
        """
        name: sample_column
        description: Oversized configuration script.
        version: 1
        """

        DATA = "{oversized_payload}"
        def detect_sample(*, **_):
            return {{"scores": {{"self": 1.0}}}}
        '''
    )

    response = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions",
        json={
            "canonical_key": "sample_column",
            "language": "python",
            "code": script,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["validation_errors"] is not None
    error_messages = payload["validation_errors"].get("code")
    assert error_messages and any("32 KiB" in message for message in error_messages)
    assert payload.get("validated_at") is None


async def test_configuration_script_validation_times_out(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Long-running scripts should be terminated and flagged."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    hanging_script = textwrap.dedent(
        '''
        """
        name: sample_column
        description: Script that never finishes executing.
        version: 1
        """

        while True:
            pass
        '''
    )

    response = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions",
        json={
            "canonical_key": "sample_column",
            "language": "python",
            "code": hanging_script,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["validation_errors"] is not None
    timeout_errors = payload["validation_errors"].get("timeout")
    assert timeout_errors and "terminated" in timeout_errors[0]
    assert payload.get("validated_at") is None


async def test_validate_script_version_requires_if_match_header(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Validation should return 428 when the If-Match header is missing."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    script_id, _ = await _create_script_version(
        async_client=async_client,
        workspace_base=workspace_base,
        configuration_id=configuration_id,
        token=token,
    )

    response = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions/{script_id}:validate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 428
    payload = response.json()
    assert payload["detail"].startswith("Precondition required")
    assert "If-Match header" in payload["detail"]


async def test_validate_script_version_requires_matching_etag(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Validation should return 412 when the If-Match header is stale."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    script_id, _ = await _create_script_version(
        async_client=async_client,
        workspace_base=workspace_base,
        configuration_id=configuration_id,
        token=token,
    )

    response = await async_client.post(
        f"{workspace_base}/configurations/{configuration_id}/scripts/sample_column/versions/{script_id}:validate",
        headers={
            "Authorization": f"Bearer {token}",
            "If-Match": 'W/"mismatch"',
        },
    )
    assert response.status_code == 412
    payload = response.json()
    assert payload["detail"].startswith("ETag mismatch")
    assert "ETag mismatch" in payload["detail"]


async def test_update_column_binding_attaches_script(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Binding a script version to a column should include metadata in the response."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    columns_response = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}/columns",
        json=[
            {
                "canonical_key": "sample_column",
                "ordinal": 0,
                "display_label": "Sample",
                "required": True,
                "enabled": True,
                "params": {},
            },
            {
                "canonical_key": "secondary",
                "ordinal": 1,
                "display_label": "Secondary",
                "required": False,
                "enabled": True,
                "params": {},
            },
        ],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert columns_response.status_code == 200, columns_response.text

    script_id, _ = await _create_script_version(
        async_client=async_client,
        workspace_base=workspace_base,
        configuration_id=configuration_id,
        token=token,
    )

    binding = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}/columns/sample_column/binding",
        json={
            "script_version_id": script_id,
            "required": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert binding.status_code == 200, binding.text
    bound = binding.json()
    assert bound["script_version"]["script_version_id"] == script_id

    mismatch = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}/columns/secondary/binding",
        json={"script_version_id": script_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mismatch.status_code == 400
    problem = mismatch.json()
    assert problem["detail"].startswith("Invalid configuration column payload")
