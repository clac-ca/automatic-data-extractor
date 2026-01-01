"""Document list filtering and validation tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_documents_unknown_param_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"unexpected": "value"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["type"] == "validation_error"
    errors = payload.get("errors") or []
    assert errors[0]["path"] == "unexpected"
    assert errors[0]["code"] == "extra_forbidden"


async def test_list_documents_invalid_filter_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "status", "operator": "eq", "value": "bogus"}]
            )
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["type"] == "validation_error"
    assert payload["detail"] == "Filter 'status' expects a supported enum value"


async def test_list_documents_uploader_me_filters(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"Authorization": f"Bearer {member_token}"}

    upload_one = await async_client.post(
        f"{workspace_base}/documents",
        headers={**member_headers, "Idempotency-Key": f"idem-{uuid4().hex}"},
        files={"file": ("member.txt", b"member", "text/plain")},
    )
    assert upload_one.status_code == 201, upload_one.text

    owner_token, _ = await login(
        async_client,
        email=owner.email,
        password=owner.password,
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    upload_two = await async_client.post(
        f"{workspace_base}/documents",
        headers={**owner_headers, "Idempotency-Key": f"idem-{uuid4().hex}"},
        files={"file": ("owner.txt", b"owner", "text/plain")},
    )
    assert upload_two.status_code == 201, upload_two.text

    # Re-authenticate as the member for filtering assertions.
    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"Authorization": f"Bearer {member_token}"}

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=member_headers,
        params={
            "filters": json.dumps(
                [{"id": "uploaderId", "operator": "eq", "value": str(member.id)}]
            )
        },
    )

    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "member.txt"
