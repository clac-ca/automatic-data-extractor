"""OpenAPI helpers for the ADE FastAPI application."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from ade_api.settings import Settings

OPENAPI_INFO_DESCRIPTION = (
    "ADE API reference. Use ReDoc at `/api` for endpoint documentation and Swagger UI at "
    "`/api/swagger` for interactive requests.\n\n"
    "Authentication supports browser session cookies and `X-API-Key` header credentials. "
    "Every response includes `X-Request-Id` for tracing and support diagnostics."
)

OPENAPI_TAG_METADATA: list[dict[str, str]] = [
    {"name": "admin-settings", "description": "Tenant-wide runtime settings and policy controls."},
    {
        "name": "api-keys",
        "description": "API key lifecycle endpoints for users and administrators.",
    },
    {"name": "auth", "description": "Interactive sign-in, password, MFA, and setup workflows."},
    {
        "name": "configurations",
        "description": "Workspace configuration package lifecycle and files.",
    },
    {
        "name": "documents",
        "description": "Document upload, metadata, listing, and streaming updates.",
    },
    {"name": "health", "description": "Service health and liveness checks."},
    {"name": "info", "description": "Runtime metadata and service identity."},
    {"name": "me", "description": "Authenticated user profile and effective permissions."},
    {"name": "meta", "description": "Installed ADE component version metadata."},
    {"name": "presence", "description": "Realtime workspace presence events and channels."},
    {"name": "rbac", "description": "Role and permission management endpoints."},
    {"name": "runs", "description": "Run creation, orchestration, output, and events."},
    {"name": "sso", "description": "Administrative SSO provider management endpoints."},
    {"name": "users", "description": "User administration endpoints."},
    {"name": "workspaces", "description": "Workspace lifecycle and membership management."},
]


def configure_openapi(app: FastAPI, settings: Settings) -> None:
    """Configure OpenAPI schema with ADE security schemes."""

    auth_security: list[dict[str, list[str]]] = [
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
        info = schema.setdefault("info", {})
        info["description"] = OPENAPI_INFO_DESCRIPTION

        public_web_url = settings.public_web_url.rstrip("/")
        servers: list[dict[str, str]] = [{"url": "/"}]
        if public_web_url and public_web_url != "/":
            servers.append({"url": public_web_url})
        schema["servers"] = servers
        schema["tags"] = [dict(tag) for tag in OPENAPI_TAG_METADATA]

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
        top_workflow_tags = {"auth", "me", "workspaces", "configurations", "documents", "runs"}
        operation_examples: dict[tuple[str, str], dict[str, Any]] = {
            (
                "/api/v1/auth/login",
                "POST",
            ): {
                "request": {
                    "application/json": {
                        "passwordLogin": {
                            "summary": "Password sign-in request",
                            "value": {
                                "email": "operator@example.com",
                                "password": "CorrectHorseBatteryStaple!",
                            },
                        }
                    }
                },
                "response": {
                    "200": {
                        "application/json": {
                            "loginSuccess": {
                                "summary": "Password sign-in success",
                                "value": {
                                    "mfaSetupRecommended": True,
                                    "mfaSetupRequired": False,
                                    "passwordChangeRequired": False,
                                },
                            },
                            "mfaChallenge": {
                                "summary": "MFA challenge required",
                                "value": {
                                    "challengeToken": (
                                        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                                        ".eyJjaGFsIjoiY2hhbGxlbmdlIn0.signature"
                                    ),
                                },
                            },
                        }
                    }
                },
            },
            (
                "/api/v1/me",
                "GET",
            ): {
                "response": {
                    "200": {
                        "application/json": {
                            "meProfile": {
                                "summary": "Authenticated profile",
                                "value": {
                                    "id": "01J7YATV4Y2R7BNS2N8MP4H2YK",
                                    "email": "operator@example.com",
                                    "displayName": "ADE Operator",
                                    "isServiceAccount": False,
                                    "isVerified": True,
                                },
                            }
                        }
                    }
                }
            },
            (
                "/api/v1/workspaces/{workspaceId}/documents",
                "POST",
            ): {
                "request": {
                    "multipart/form-data": {
                        "uploadDocument": {
                            "summary": "Upload and queue with active sheet only",
                            "value": {
                                "metadata": '{"source":"api-guide","mode":"active-sheet-only"}',
                                "run_options": '{"activeSheetOnly":true}',
                                "conflictMode": "keep_both",
                            },
                        }
                    }
                },
                "response": {
                    "201": {
                        "application/json": {
                            "uploadedDocument": {
                                "summary": "Uploaded document",
                                "value": {
                                    "id": "01J7YB4D2YQ35XQB7AVJH8GWWV",
                                    "workspaceId": "01J7YAX69V8ACZ8SBRJ8GHXW1A",
                                    "name": "input.xlsx",
                                    "byteSize": 12482,
                                    "metadata": {
                                        "source": "api-guide",
                                        "mode": "active-sheet-only",
                                    },
                                },
                            }
                        }
                    }
                },
            },
            (
                "/api/v1/workspaces/{workspaceId}/runs",
                "POST",
            ): {
                "request": {
                    "application/json": {
                        "processDocumentRun": {
                            "summary": "Create a run for one uploaded document",
                            "value": {
                                "inputDocumentId": "01J7YB4D2YQ35XQB7AVJH8GWWV",
                                "options": {
                                    "operation": "process",
                                    "activeSheetOnly": True,
                                },
                            },
                        }
                    }
                },
                "response": {
                    "201": {
                        "application/json": {
                            "createdRun": {
                                "summary": "Queued run",
                                "value": {
                                    "id": "01J7YB9A6Y3QFNBVE9S9THQ4HC",
                                    "workspaceId": "01J7YAX69V8ACZ8SBRJ8GHXW1A",
                                    "status": "queued",
                                    "operation": "process",
                                },
                            }
                        }
                    }
                },
            },
            (
                "/api/v1/workspaces/{workspaceId}/configurations",
                "POST",
            ): {
                "request": {
                    "application/json": {
                        "createFromTemplate": {
                            "summary": "Create a draft configuration from template",
                            "value": {
                                "displayName": "Customer Imports v2",
                                "source": {"type": "template"},
                                "notes": "Initial draft for spreadsheet normalization.",
                            },
                        }
                    }
                },
                "response": {
                    "201": {
                        "application/json": {
                            "configurationRecord": {
                                "summary": "Created draft configuration",
                                "value": {
                                    "id": "01J7YC64V8M7CJWVJCE2R9VW5G",
                                    "workspaceId": "01J7YAX69V8ACZ8SBRJ8GHXW1A",
                                    "displayName": "Customer Imports v2",
                                    "status": "draft",
                                },
                            }
                        }
                    }
                },
            },
        }

        def _add_parameter(operation: dict[str, Any], ref: str, name: str | None = None) -> None:
            params = operation.setdefault("parameters", [])
            if not isinstance(params, list):
                return
            if any(isinstance(item, dict) and item.get("$ref") == ref for item in params):
                return
            if name and any(
                isinstance(item, dict) and item.get("name") == name and item.get("in") == "header"
                for item in params
            ):
                return
            params.append({"$ref": ref})

        def _set_examples(
            operation: dict[str, Any],
            *,
            request: dict[str, dict[str, Any]] | None = None,
            response: dict[str, dict[str, dict[str, Any]]] | None = None,
        ) -> None:
            if request:
                request_body = operation.setdefault("requestBody", {})
                if not isinstance(request_body, dict):
                    request_body = {}
                    operation["requestBody"] = request_body
                content = request_body.setdefault("content", {})
                if not isinstance(content, dict):
                    content = {}
                    request_body["content"] = content
                for media_type, examples in request.items():
                    media = content.setdefault(media_type, {})
                    if not isinstance(media, dict) or "examples" in media:
                        continue
                    media["examples"] = examples

            if response:
                responses = operation.setdefault("responses", {})
                if not isinstance(responses, dict):
                    return
                for status_code, media_by_type in response.items():
                    response_obj = responses.get(status_code)
                    if not isinstance(response_obj, dict) or "$ref" in response_obj:
                        continue
                    content = response_obj.setdefault("content", {})
                    if not isinstance(content, dict):
                        continue
                    for media_type, examples in media_by_type.items():
                        media = content.setdefault(media_type, {})
                        if not isinstance(media, dict) or "examples" in media:
                            continue
                        media["examples"] = examples

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

                raw_tags = [str(tag) for tag in operation.get("tags", []) if isinstance(tag, str)]
                if raw_tags:
                    operation["tags"] = sorted(dict.fromkeys(raw_tags))
                tags = {tag for tag in operation.get("tags", []) if isinstance(tag, str)}
                if tags.intersection(top_workflow_tags) and not operation.get("description"):
                    summary = str(operation.get("summary", "")).strip()
                    if summary:
                        operation["description"] = f"{summary}."

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

                operation_example = operation_examples.get((path, method_upper))
                if operation_example:
                    _set_examples(
                        operation,
                        request=operation_example.get("request"),
                        response=operation_example.get("response"),
                    )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


__all__ = ["configure_openapi"]
