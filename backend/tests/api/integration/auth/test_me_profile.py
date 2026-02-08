from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_patch_me_updates_display_name(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    member = seed_identity.member

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert login.status_code == 200, login.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    update = await async_client.patch(
        "/api/v1/me",
        json={"display_name": "Data Ops Specialist"},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert update.status_code == 200, update.text
    payload = update.json()
    assert payload["display_name"] == "Data Ops Specialist"

    me = await async_client.get("/api/v1/me")
    assert me.status_code == 200, me.text
    assert me.json()["display_name"] == "Data Ops Specialist"


async def test_patch_me_requires_editable_fields(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    member = seed_identity.member
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert login.status_code == 200, login.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    update = await async_client.patch(
        "/api/v1/me",
        json={},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert update.status_code == 422, update.text


async def test_patch_me_requires_csrf_for_cookie_auth(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert login.status_code == 200, login.text

    update = await async_client.patch(
        "/api/v1/me",
        json={"display_name": "No CSRF"},
    )
    assert update.status_code == 403, update.text
