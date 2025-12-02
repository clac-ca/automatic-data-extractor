"""OpenAPI helpers for the ADE FastAPI application."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from ade_api.settings import Settings


def configure_openapi(app: FastAPI, settings: Settings) -> None:
    """Configure OpenAPI schema with ADE security schemes."""

    auth_security = [
        {"SessionCookie": []},
        {"HTTPBearer": []},
        {"APIKeyHeader": []},
    ]
    public_routes: set[tuple[str, str]] = {
        ("/api/v1/health", "GET"),
        ("/api/v1/auth/providers", "GET"),
        ("/api/v1/auth/setup", "GET"),
        ("/api/v1/auth/setup", "POST"),
        ("/api/v1/auth/session", "POST"),
        ("/api/v1/auth/sso/{provider}/authorize", "GET"),
        ("/api/v1/auth/sso/{provider}/callback", "GET"),
    }
    http_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}

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

        schema["security"] = auth_security

        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                if not isinstance(operation, dict):
                    continue
                method_upper = method.upper()
                if method_upper not in http_methods:
                    continue
                if (path, method_upper) in public_routes:
                    operation["security"] = []
                else:
                    if "security" not in operation or operation["security"] is None:
                        operation["security"] = list(auth_security)

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


__all__ = ["configure_openapi"]
