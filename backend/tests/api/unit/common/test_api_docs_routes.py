from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ade_api.core.auth import AuthenticationError
from ade_api.core.http import require_authenticated
from ade_api.main import create_app
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


def _raise_authentication_error() -> object:
    raise AuthenticationError("Authentication required")


def _build_settings(
    *,
    api_docs_enabled: bool,
    api_docs_access_mode: str = "authenticated",
) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
        api_docs_enabled=api_docs_enabled,
        api_docs_access_mode=api_docs_access_mode,
    )


async def test_api_docs_routes_are_disabled_by_default() -> None:
    app = create_app(settings=_build_settings(api_docs_enabled=False))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        for path in (
            "/api",
            "/api/docs",
            "/api/swagger",
            "/api/openapi.json",
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            response = await client.get(path, follow_redirects=False)
            assert response.status_code == 404


async def test_api_docs_routes_are_exposed_when_enabled_in_public_mode() -> None:
    app = create_app(
        settings=_build_settings(api_docs_enabled=True, api_docs_access_mode="public")
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        redoc = await client.get("/api")
        assert redoc.status_code == 200
        assert redoc.headers["content-type"].startswith("text/html")
        assert "redoc" in redoc.text.lower()
        assert redoc.headers["cache-control"] == "no-store"
        assert redoc.headers["x-robots-tag"] == "noindex, nofollow"

        swagger = await client.get("/api/swagger")
        assert swagger.status_code == 200
        assert swagger.headers["content-type"].startswith("text/html")
        assert "swagger ui" in swagger.text.lower()
        assert swagger.headers["cache-control"] == "no-store"
        assert swagger.headers["x-robots-tag"] == "noindex, nofollow"

        openapi = await client.get("/api/openapi.json")
        assert openapi.status_code == 200
        assert openapi.headers["content-type"].startswith("application/json")
        assert openapi.headers["cache-control"] == "no-store"
        assert openapi.headers["x-robots-tag"] == "noindex, nofollow"
        payload = openapi.json()
        assert payload["openapi"].startswith("3.")


async def test_api_docs_routes_require_authentication_by_default() -> None:
    app = create_app(settings=_build_settings(api_docs_enabled=True))
    app.dependency_overrides[require_authenticated] = _raise_authentication_error

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        redirect_expectations = {
            "/api": "/login?returnTo=%2Fapi",
            "/api/swagger": "/login?returnTo=%2Fapi%2Fswagger",
            "/api/openapi.json": "/login?returnTo=%2Fapi%2Fopenapi.json",
            "/api/docs": "/login?returnTo=%2Fapi%2Fdocs",
            "/docs": "/login?returnTo=%2Fdocs",
            "/redoc": "/login?returnTo=%2Fredoc",
            "/openapi.json": "/login?returnTo=%2Fopenapi.json",
        }
        for path, expected_location in redirect_expectations.items():
            response = await client.get(path, follow_redirects=False)
            assert response.status_code == 307
            assert response.headers["location"] == expected_location


async def test_docs_auth_redirect_preserves_query_string_in_return_to() -> None:
    app = create_app(settings=_build_settings(api_docs_enabled=True))
    app.dependency_overrides[require_authenticated] = _raise_authentication_error

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/swagger?tag=runs", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/login?returnTo=%2Fapi%2Fswagger%3Ftag%3Druns"


async def test_legacy_api_docs_routes_redirect_to_canonical_paths_when_authenticated() -> None:
    app = create_app(settings=_build_settings(api_docs_enabled=True))
    app.dependency_overrides[require_authenticated] = lambda: object()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        assert (await client.get("/api")).status_code == 200
        assert (await client.get("/api/swagger")).status_code == 200
        assert (await client.get("/api/openapi.json")).status_code == 200

        redirect_expectations = {
            "/api/docs": "/api/swagger",
            "/docs": "/api/swagger",
            "/redoc": "/api",
            "/openapi.json": "/api/openapi.json",
        }

        for source, target in redirect_expectations.items():
            response = await client.get(source, follow_redirects=False)
            assert response.status_code == 307
            assert response.headers["location"] == target
