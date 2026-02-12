from __future__ import annotations

import json
from typing import Any

from ade_api.main import create_app
from ade_api.scripts.generate_openapi import CANONICAL_SERVER_URL
from ade_api.settings import Settings
from paths import REPO_ROOT

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


def _build_settings(*, public_web_url: str = "https://ade.example.test") -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
        public_web_url=public_web_url,
    )


def _openapi_schema(*, public_web_url: str = "https://ade.example.test") -> dict[str, Any]:
    app = create_app(settings=_build_settings(public_web_url=public_web_url))
    return app.openapi()


def test_openapi_servers_prefer_same_origin_then_public_url() -> None:
    schema = _openapi_schema(public_web_url="https://ade.example.test")
    servers = schema.get("servers", [])

    assert isinstance(servers, list)
    assert servers[0]["url"] == "/"
    assert servers[1]["url"] == "https://ade.example.test"


def test_openapi_operations_have_deduplicated_sorted_tags() -> None:
    schema = _openapi_schema(public_web_url="https://ade.example.test")
    paths = schema.get("paths", {})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.upper() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            tags = operation.get("tags", [])
            normalized_tags = [tag for tag in tags if isinstance(tag, str)]
            assert len(normalized_tags) == len(set(normalized_tags)), f"{method.upper()} {path}"
            assert normalized_tags == sorted(normalized_tags), f"{method.upper()} {path}"


def test_openapi_exposes_expected_tag_metadata_and_security_schemes() -> None:
    schema = _openapi_schema(public_web_url="https://ade.example.test")

    tags = schema.get("tags", [])
    tag_names = {entry["name"] for entry in tags if isinstance(entry, dict) and "name" in entry}
    expected_tags = {
        "admin-settings",
        "api-keys",
        "auth",
        "configurations",
        "documents",
        "health",
        "info",
        "me",
        "meta",
        "presence",
        "rbac",
        "runs",
        "sso",
        "users",
        "workspaces",
    }
    assert expected_tags.issubset(tag_names)

    security_schemes = (
        schema.get("components", {})
        .get("securitySchemes", {})
    )
    assert "SessionCookie" in security_schemes
    assert "APIKeyHeader" in security_schemes


def test_role_assignment_delete_does_not_require_if_match_header() -> None:
    schema = _openapi_schema(public_web_url="https://ade.example.test")
    operation = schema["paths"]["/api/v1/roleAssignments/{assignmentId}"]["delete"]
    parameters = operation.get("parameters", [])
    components = schema.get("components", {}).get("parameters", {})

    header_names: set[str] = set()
    for parameter in parameters:
        if "$ref" in parameter:
            ref = str(parameter["$ref"])
            ref_name = ref.rsplit("/", 1)[-1]
            resolved = components.get(ref_name, {})
            if resolved.get("in") == "header" and isinstance(resolved.get("name"), str):
                header_names.add(resolved["name"])
            continue

        if parameter.get("in") == "header" and isinstance(parameter.get("name"), str):
            header_names.add(parameter["name"])

    assert "If-Match" not in header_names


def test_generated_openapi_file_matches_runtime_schema() -> None:
    schema = _openapi_schema(public_web_url=CANONICAL_SERVER_URL)
    schema["servers"] = [{"url": CANONICAL_SERVER_URL}]
    generated_path = REPO_ROOT / "backend" / "src" / "ade_api" / "openapi.json"
    generated_schema = json.loads(generated_path.read_text(encoding="utf-8"))

    assert generated_schema == schema
