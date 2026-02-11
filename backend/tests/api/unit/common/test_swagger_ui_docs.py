from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ade_api.common.api_docs import SWAGGER_REQUEST_INTERCEPTOR_MARKER
from ade_api.main import create_app
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


def _build_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
        api_docs_enabled=True,
        api_docs_access_mode="public",
    )


async def test_swagger_ui_contains_expected_dev_configuration() -> None:
    app = create_app(settings=_build_settings())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/swagger")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "tryItOutEnabled" in html
    assert "displayRequestDuration" in html
    assert "persistAuthorization" in html
    assert "displayOperationId" in html
    assert "defaultModelsExpandDepth" in html
    assert "operationsSorter" in html
    assert "tagsSorter" in html


async def test_swagger_ui_injects_csrf_request_interceptor() -> None:
    app = create_app(settings=_build_settings())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/swagger")

    assert response.status_code == 200
    html = response.text
    assert SWAGGER_REQUEST_INTERCEPTOR_MARKER in html
    assert "X-CSRF-Token" in html
    assert "requestInterceptor" in html
    assert "ade_csrf" in html
