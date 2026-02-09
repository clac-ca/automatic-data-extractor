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
        {"APIKeyHeader": []},
    ]
    public_routes: set[tuple[str, str]] = {
        ("/api/v1/health", "GET"),
        ("/api/v1/info", "GET"),
        ("/api/v1/auth/providers", "GET"),
        ("/api/v1/auth/sso/providers", "GET"),
        ("/api/v1/auth/setup", "GET"),
        ("/api/v1/auth/setup", "POST"),
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/auth/password/forgot", "POST"),
        ("/api/v1/auth/password/reset", "POST"),
        ("/api/v1/auth/mfa/challenge/verify", "POST"),
        ("/api/v1/auth/sso/authorize", "GET"),
        ("/api/v1/auth/sso/callback", "GET"),
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
        schema["servers"] = [{"url": settings.public_web_url}]

        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["SessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.session_cookie_name,
            "description": "Browser session cookie issued after interactive sign-in.",
        }
        security_schemes.setdefault(
            "APIKeyHeader",
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "Static API key for service integrations.",
            },
        )

        schemas = components.setdefault("schemas", {})
        schemas.setdefault(
            "ProblemDetailsErrorItem",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "nullable": True},
                    "message": {"type": "string"},
                    "code": {"type": "string", "nullable": True},
                },
                "required": ["message"],
            },
        )
        schemas.setdefault(
            "ProblemDetails",
            {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "integer"},
                    "detail": {
                        "nullable": True,
                        "anyOf": [
                            {"type": "string"},
                            {"type": "object", "additionalProperties": True},
                        ],
                    },
                    "instance": {"type": "string"},
                    "requestId": {"type": "string", "nullable": True},
                    "errors": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ProblemDetailsErrorItem"},
                        "nullable": True,
                    },
                },
                "required": ["type", "title", "status", "instance"],
            },
        )

        headers = components.setdefault("headers", {})
        headers.setdefault(
            "X-Request-Id",
            {
                "schema": {"type": "string"},
                "description": "Unique request identifier for tracing and support.",
            },
        )
        headers.setdefault(
            "ETag",
            {
                "schema": {"type": "string"},
                "description": "Entity tag for the current representation.",
            },
        )

        responses = components.setdefault("responses", {})
        responses.setdefault(
            "ProblemDetails",
            {
                "description": "Problem Details error response.",
                "headers": {
                    "X-Request-Id": {"$ref": "#/components/headers/X-Request-Id"},
                },
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/ProblemDetails"},
                    }
                },
            },
        )

        parameters = components.setdefault("parameters", {})
        parameters.setdefault(
            "IfMatch",
            {
                "name": "If-Match",
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": "ETag value required for optimistic concurrency checks.",
            },
        )

        schema["security"] = auth_security

        etag_routes = {
            ("/api/v1/workspaces/{workspaceId}/configurations/{configurationId}", "GET"),
            ("/api/v1/users/me/apikeys/{apiKeyId}", "GET"),
            ("/api/v1/users/{userId}/apikeys/{apiKeyId}", "GET"),
            ("/api/v1/workspaces/{workspaceId}/roles/{roleId}", "GET"),
            ("/api/v1/workspaces/{workspaceId}/roleassignments/{assignmentId}", "GET"),
        }
        if_match_routes = {
            ("/api/v1/workspaces/{workspaceId}/roles/{roleId}", "PATCH"),
            ("/api/v1/workspaces/{workspaceId}/roles/{roleId}", "DELETE"),
            ("/api/v1/workspaces/{workspaceId}/roleassignments/{assignmentId}", "DELETE"),
            ("/api/v1/users/me/apikeys/{apiKeyId}", "DELETE"),
            ("/api/v1/users/{userId}/apikeys/{apiKeyId}", "DELETE"),
        }

        def _add_parameter(operation: dict[str, Any], ref: str, name: str | None = None) -> None:
            params = operation.setdefault("parameters", [])
            if not isinstance(params, list):
                return
            if any(isinstance(item, dict) and item.get("$ref") == ref for item in params):
                return
            if name and any(
                isinstance(item, dict)
                and item.get("name") == name
                and item.get("in") == "header"
                for item in params
            ):
                return
            params.append({"$ref": ref})

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

                responses = operation.setdefault("responses", {})
                responses.setdefault("default", {"$ref": "#/components/responses/ProblemDetails"})

                for response in responses.values():
                    if not isinstance(response, dict) or "$ref" in response:
                        continue
                    headers = response.setdefault("headers", {})
                    headers.setdefault(
                        "X-Request-Id",
                        {"$ref": "#/components/headers/X-Request-Id"},
                    )

                if (path, method_upper) in etag_routes:
                    for status_code, response in responses.items():
                        if not isinstance(response, dict) or "$ref" in response:
                            continue
                        if (
                            isinstance(status_code, str)
                            and status_code.isdigit()
                            and status_code.startswith("2")
                        ):
                            headers = response.setdefault("headers", {})
                            headers.setdefault("ETag", {"$ref": "#/components/headers/ETag"})

                if (path, method_upper) in if_match_routes:
                    _add_parameter(operation, "#/components/parameters/IfMatch", "If-Match")

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


__all__ = ["configure_openapi"]
