"""Document update endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_update_document_rename_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "before-rename.xlsx",
                b"payload",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    rename = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
        json={"name": "Quarterly Intake.xlsx"},
    )
    assert rename.status_code == 200, rename.text
    renamed_payload = rename.json()
    assert renamed_payload["id"] == document_id
    assert renamed_payload["name"] == "Quarterly Intake.xlsx"

    detail = await async_client.get(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Quarterly Intake.xlsx"


async def test_update_document_rename_conflict_returns_409(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    first_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "existing-name.xlsx",
                b"first",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert first_upload.status_code == 201, first_upload.text

    second_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "target.xlsx",
                b"second",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert second_upload.status_code == 201, second_upload.text
    second_document_id = second_upload.json()["id"]

    rename = await async_client.patch(
        f"{workspace_base}/documents/{second_document_id}",
        headers=headers,
        json={"name": "existing-name.xlsx"},
    )
    assert rename.status_code == 409, rename.text
    assert "already in use" in rename.json()["detail"]


async def test_update_document_rename_extension_change_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "rename-source.xlsx",
                b"payload",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    rename = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
        json={"name": "rename-source.csv"},
    )
    assert rename.status_code == 422, rename.text
    assert rename.json()["detail"] == "File extension cannot be changed."


async def test_update_document_rename_whitespace_only_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "whitespace.xlsx",
                b"payload",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    rename = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
        json={"name": "   "},
    )
    assert rename.status_code == 422, rename.text
