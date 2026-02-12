from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from ade_api.features.batch.schemas import BatchSubrequest
from ade_api.features.batch.service import parse_batch_operation, validate_batch_dependencies


def _req(
    request_id: str,
    *,
    method: str = "POST",
    url: str = "/users",
    depends_on: list[str] | None = None,
) -> BatchSubrequest:
    return BatchSubrequest(
        id=request_id,
        method=method,
        url=url,
        dependsOn=depends_on or [],
        body={},
    )


def test_parse_batch_operation_supports_create_user() -> None:
    parsed = parse_batch_operation(method="POST", url="/users")
    assert parsed.kind == "create_user"
    assert parsed.user_id is None


def test_parse_batch_operation_supports_update_user() -> None:
    user_id = uuid4()
    parsed = parse_batch_operation(method="PATCH", url=f"/users/{user_id}")
    assert parsed.kind == "update_user"
    assert parsed.user_id == user_id


def test_parse_batch_operation_supports_deactivate_user() -> None:
    user_id = uuid4()
    parsed = parse_batch_operation(method="POST", url=f"/users/{user_id}/deactivate")
    assert parsed.kind == "deactivate_user"
    assert parsed.user_id == user_id


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/users"),
        ("PATCH", "/users/not-a-uuid"),
        ("POST", "https://example.com/users"),
        ("DELETE", "/users"),
        ("POST", "/groups"),
    ],
)
def test_parse_batch_operation_rejects_unsupported_routes(method: str, url: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_batch_operation(method=method, url=url)
    assert exc_info.value.status_code == 422


def test_validate_batch_dependencies_accepts_valid_dependency_graph() -> None:
    requests = [
        _req("1"),
        _req("2", depends_on=["1"]),
        _req("3", depends_on=["2"]),
    ]
    validate_batch_dependencies(requests)


def test_validate_batch_dependencies_rejects_duplicate_ids() -> None:
    requests = [_req("same"), _req("same")]
    with pytest.raises(HTTPException) as exc_info:
        validate_batch_dependencies(requests)
    assert exc_info.value.status_code == 422
    assert "must be unique" in str(exc_info.value.detail)


def test_validate_batch_dependencies_rejects_unknown_dependency() -> None:
    requests = [_req("one", depends_on=["missing"])]
    with pytest.raises(HTTPException) as exc_info:
        validate_batch_dependencies(requests)
    assert exc_info.value.status_code == 422
    assert "Unknown dependency id" in str(exc_info.value.detail)


def test_validate_batch_dependencies_rejects_self_dependency() -> None:
    requests = [_req("one", depends_on=["one"])]
    with pytest.raises(HTTPException) as exc_info:
        validate_batch_dependencies(requests)
    assert exc_info.value.status_code == 422
    assert "cannot depend on itself" in str(exc_info.value.detail)


def test_validate_batch_dependencies_rejects_cycles() -> None:
    requests = [
        _req("one", depends_on=["two"]),
        _req("two", depends_on=["one"]),
    ]
    with pytest.raises(HTTPException) as exc_info:
        validate_batch_dependencies(requests)
    assert exc_info.value.status_code == 422
    assert "cycle" in str(exc_info.value.detail).lower()
