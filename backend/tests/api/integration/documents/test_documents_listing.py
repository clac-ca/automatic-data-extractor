"""Document list filtering and validation tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(async_client: AsyncClient, user) -> dict[str, str]:
    token, _ = await login(async_client, email=user.email, password=user.password)
    return {"X-API-Key": token}


def _mention_payload(body: str, label: str, user_id: str) -> dict[str, object]:
    start = body.index(label)
    return {
        "userId": str(user_id),
        "start": start,
        "end": start + len(label),
    }


async def test_list_documents_unknown_param_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

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
    headers = {"X-API-Key": token}

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "lastRunPhase", "operator": "eq", "value": "bogus"}]
            )
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["type"] == "validation_error"
    assert payload["detail"] == "Invalid lastRunPhase value(s): bogus"


async def test_list_documents_uploader_me_filters(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"X-API-Key": member_token}

    upload_one = await async_client.post(
        f"{workspace_base}/documents",
        headers=member_headers,
        files={"file": ("member.txt", b"member", "text/plain")},
    )
    assert upload_one.status_code == 201, upload_one.text

    owner_token, _ = await login(
        async_client,
        email=owner.email,
        password=owner.password,
    )
    owner_headers = {"X-API-Key": owner_token}

    upload_two = await async_client.post(
        f"{workspace_base}/documents",
        headers=owner_headers,
        files={"file": ("owner.txt", b"owner", "text/plain")},
    )
    assert upload_two.status_code == 201, upload_two.text

    # Re-authenticate as the member for filtering assertions.
    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"X-API-Key": member_token}

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


async def test_list_documents_id_in_filter(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    doc_one = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delta-one.txt", b"one", "text/plain")},
    )
    assert doc_one.status_code == 201, doc_one.text
    doc_two = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delta-two.txt", b"two", "text/plain")},
    )
    assert doc_two.status_code == 201, doc_two.text

    id_one = doc_one.json()["id"]
    id_two = doc_two.json()["id"]

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "id", "operator": "in", "value": [id_one, id_two]}]
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    returned_ids = sorted([item["id"] for item in payload["items"]])
    assert returned_ids == sorted([id_one, id_two])


async def test_list_documents_page_mode_returns_requested_page_and_total(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    headers = await _auth_headers(async_client, seed_identity.member)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    for index in range(1, 6):
        response = await async_client.post(
            f"{workspace_base}/documents",
            headers=headers,
            files={
                "file": (
                    f"page-{index:02d}.txt",
                    f"file-{index}".encode("utf-8"),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 201, response.text

    sort = json.dumps([{"id": "name", "desc": False}])
    middle_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "page": 2,
            "limit": 2,
            "sort": sort,
            "includeTotal": True,
        },
    )

    assert middle_page.status_code == 200, middle_page.text
    payload = middle_page.json()
    assert [item["name"] for item in payload["items"]] == ["page-03.txt", "page-04.txt"]
    assert payload["meta"]["totalCount"] == 5
    assert payload["meta"]["hasMore"] is True

    last_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "page": 3,
            "limit": 2,
            "sort": sort,
            "includeTotal": True,
        },
    )

    assert last_page.status_code == 200, last_page.text
    last_payload = last_page.json()
    assert [item["name"] for item in last_payload["items"]] == ["page-05.txt"]
    assert last_payload["meta"]["totalCount"] == 5
    assert last_payload["meta"]["hasMore"] is False


async def test_list_documents_page_mode_rejects_cursor_and_returns_empty_out_of_range_page(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    headers = await _auth_headers(async_client, seed_identity.member)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    first_doc = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("alpha-page.txt", b"alpha", "text/plain")},
    )
    assert first_doc.status_code == 201, first_doc.text

    second_doc = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("beta-page.txt", b"beta", "text/plain")},
    )
    assert second_doc.status_code == 201, second_doc.text

    cursor_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"limit": 1},
    )
    assert cursor_page.status_code == 200, cursor_page.text
    next_cursor = cursor_page.json()["meta"]["nextCursor"]
    assert isinstance(next_cursor, str)

    mixed = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"page": 2, "limit": 1, "cursor": next_cursor},
    )

    assert mixed.status_code == 422, mixed.text
    assert mixed.json()["detail"] == "Query parameters 'page' and 'cursor' cannot be used together."

    empty_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "page": 2,
            "limit": 1,
            "includeTotal": True,
            "filters": json.dumps(
                [{"id": "name", "operator": "eq", "value": "alpha-page.txt"}]
            ),
        },
    )

    assert empty_page.status_code == 200, empty_page.text
    payload = empty_page.json()
    assert payload["items"] == []
    assert payload["meta"]["totalCount"] == 1
    assert payload["meta"]["hasMore"] is False


async def test_list_documents_cursor_mode_still_supports_next_cursor(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    headers = await _auth_headers(async_client, seed_identity.member)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    sort = json.dumps([{"id": "name", "desc": False}])

    for name in ("cursor-alpha.txt", "cursor-beta.txt"):
        response = await async_client.post(
            f"{workspace_base}/documents",
            headers=headers,
            files={"file": (name, name.encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 201, response.text

    first_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"limit": 1, "sort": sort},
    )

    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    assert [item["name"] for item in first_payload["items"]] == ["cursor-alpha.txt"]
    next_cursor = first_payload["meta"]["nextCursor"]
    assert isinstance(next_cursor, str)

    second_page = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"limit": 1, "sort": sort, "cursor": next_cursor},
    )

    assert second_page.status_code == 200, second_page.text
    second_payload = second_page.json()
    assert [item["name"] for item in second_payload["items"]] == ["cursor-beta.txt"]


async def test_list_documents_filters_by_mentioned_user(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    author = seed_identity.member
    mentioned = seed_identity.member_with_manage
    another = seed_identity.workspace_owner
    headers = await _auth_headers(async_client, author)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    first_doc = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("mention-one.txt", b"one", "text/plain")},
    )
    assert first_doc.status_code == 201, first_doc.text
    first_id = first_doc.json()["id"]

    second_doc = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("mention-two.txt", b"two", "text/plain")},
    )
    assert second_doc.status_code == 201, second_doc.text

    third_doc = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("mention-three.txt", b"three", "text/plain")},
    )
    assert third_doc.status_code == 201, third_doc.text
    third_id = third_doc.json()["id"]

    first_label = f"@{mentioned.email}"
    first_body = f"Please review {first_label}"
    created_first_thread = await async_client.post(
        f"{workspace_base}/documents/{first_id}/threads",
        headers=headers,
        json={
            "anchorType": "note",
            "body": first_body,
            "mentions": [_mention_payload(first_body, first_label, mentioned.id)],
        },
    )
    assert created_first_thread.status_code == 201, created_first_thread.text

    third_label = f"@{another.email}"
    third_body = f"Loop in {third_label}"
    created_third_thread = await async_client.post(
        f"{workspace_base}/documents/{third_id}/threads",
        headers=headers,
        json={
            "anchorType": "note",
            "body": third_body,
            "mentions": [_mention_payload(third_body, third_label, another.id)],
        },
    )
    assert created_third_thread.status_code == 201, created_third_thread.text

    mentioned_only = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "sort": json.dumps([{"id": "name", "desc": False}]),
            "filters": json.dumps(
                [{"id": "mentionedUserId", "operator": "eq", "value": str(mentioned.id)}]
            ),
        },
    )

    assert mentioned_only.status_code == 200, mentioned_only.text
    assert [item["name"] for item in mentioned_only.json()["items"]] == ["mention-one.txt"]

    any_mentioned = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "sort": json.dumps([{"id": "name", "desc": False}]),
            "filters": json.dumps(
                [
                    {
                        "id": "mentionedUserId",
                        "operator": "in",
                        "value": [str(mentioned.id), str(another.id)],
                    }
                ]
            ),
        },
    )

    assert any_mentioned.status_code == 200, any_mentioned.text
    assert [item["name"] for item in any_mentioned.json()["items"]] == [
        "mention-one.txt",
        "mention-three.txt",
    ]

    no_mentions = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "sort": json.dumps([{"id": "name", "desc": False}]),
            "filters": json.dumps(
                [{"id": "mentionedUserId", "operator": "isEmpty"}]
            ),
        },
    )

    assert no_mentions.status_code == 200, no_mentions.text
    assert [item["name"] for item in no_mentions.json()["items"]] == ["mention-two.txt"]

    archive = await async_client.post(
        f"{workspace_base}/documents/{first_id}/archive",
        headers=headers,
    )
    assert archive.status_code == 204, archive.text

    archived_mentions = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "lifecycle": "archived",
            "filters": json.dumps(
                [{"id": "mentionedUserId", "operator": "eq", "value": str(mentioned.id)}]
            ),
        },
    )

    assert archived_mentions.status_code == 200, archived_mentions.text
    assert [item["id"] for item in archived_mentions.json()["items"]] == [first_id]

    non_member = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "mentionedUserId", "operator": "eq", "value": str(uuid4())}]
            ),
        },
    )

    assert non_member.status_code == 200, non_member.text
    assert non_member.json()["items"] == []

    invalid = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "mentionedUserId", "operator": "eq", "value": "not-a-uuid"}]
            ),
        },
    )

    assert invalid.status_code == 422, invalid.text
