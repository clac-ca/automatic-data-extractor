"""OpenAPI helpers for the ADE FastAPI application."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from apps.api.app.settings import Settings


def configure_openapi(app: FastAPI, settings: Settings) -> None:
    """Configure OpenAPI schema with ADE security schemes."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["servers"] = [{"url": settings.server_public_url}]

        components = schema.setdefault("components", {}).setdefault(
            "securitySchemes",
            {},
        )
        components["SessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.session_cookie_name,
            "description": "Browser session cookie issued after interactive sign-in.",
        }
        components.setdefault(
            "HTTPBearer",
            {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Bearer access token returned by ADE or an identity provider.",
            },
        )
        components.setdefault(
            "APIKeyHeader",
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "Static API key for service integrations.",
            },
        )

        schema["security"] = [
            {"SessionCookie": []},
            {"HTTPBearer": []},
            {"APIKeyHeader": []},
        ]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


__all__ = ["configure_openapi"]
