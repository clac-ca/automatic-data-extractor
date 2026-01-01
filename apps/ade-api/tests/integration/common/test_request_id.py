"""Integration tests for request ID propagation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_request_id_echoes_header(async_client: AsyncClient) -> None:
    response = await async_client.get("/health", headers={"X-Request-Id": "req_test"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == "req_test"


async def test_request_id_generated_when_missing(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")

    assert response.status_code == 200
    header = response.headers.get("X-Request-Id")
    assert header is not None
    assert header.startswith("req_")


async def test_request_id_in_error_response(async_client: AsyncClient) -> None:
    response = await async_client.post("/health", headers={"X-Request-Id": "req_error"})

    assert response.status_code == 405
    assert response.headers.get("X-Request-Id") == "req_error"
    payload = response.json()
    assert payload["requestId"] == "req_error"
