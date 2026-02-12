"""Batch execution service for access-management mutations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ade_api.common.logging import log_context
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.rbac.service_interface import RbacService
from ade_api.features.users.schemas import UserCreate, UserCreateResponse, UserOut, UserUpdate
from ade_api.features.users.service import UsersService
from ade_api.settings import Settings
from ade_db.models import User

from .schemas import BatchRequest, BatchResponse, BatchSubrequest, BatchSubresponse

logger = logging.getLogger(__name__)

_ALLOWED_METHODS = {"POST", "PATCH"}


@dataclass(frozen=True, slots=True)
class ParsedBatchOperation:
    """Normalized operation parsed from a subrequest."""

    kind: Literal["create_user", "update_user", "deactivate_user"]
    user_id: UUID | None = None


def _parse_uuid_from_path(path: str, *, suffix: str = "") -> UUID | None:
    token = path.removeprefix("/users/")
    if suffix:
        token = token.removesuffix(suffix)
    token = token.strip()
    try:
        return UUID(token)
    except (TypeError, ValueError):
        return None


def parse_batch_operation(*, method: str, url: str) -> ParsedBatchOperation:
    """Parse and validate a supported subrequest operation."""

    normalized_method = method.strip().upper()
    if normalized_method not in _ALLOWED_METHODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported batch method: {method!r}.",
        )

    normalized_url = url.strip()
    if not normalized_url.startswith("/"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Batch subrequest URLs must be relative paths.",
        )

    if normalized_method == "POST" and normalized_url == "/users":
        return ParsedBatchOperation(kind="create_user")

    if normalized_method == "PATCH" and normalized_url.startswith("/users/"):
        user_id = _parse_uuid_from_path(normalized_url)
        if user_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported batch URL: {url!r}.",
            )
        return ParsedBatchOperation(kind="update_user", user_id=user_id)

    if normalized_method == "POST" and normalized_url.endswith("/deactivate"):
        if not normalized_url.startswith("/users/"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported batch URL: {url!r}.",
            )
        user_id = _parse_uuid_from_path(normalized_url, suffix="/deactivate")
        if user_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported batch URL: {url!r}.",
            )
        return ParsedBatchOperation(kind="deactivate_user", user_id=user_id)

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported batch URL/method combination: {method.upper()} {url}",
    )


def validate_batch_dependencies(requests: list[BatchSubrequest]) -> None:
    """Validate request ids and dependency graph structure."""

    ids = [request.id for request in requests]
    unique_ids = set(ids)
    if len(unique_ids) != len(ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Batch subrequest ids must be unique.",
        )

    for request in requests:
        for dependency_id in request.depends_on:
            if dependency_id not in unique_ids:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Unknown dependency id '{dependency_id}' for request '{request.id}'.",
                )
            if dependency_id == request.id:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Request '{request.id}' cannot depend on itself.",
                )

    adjacency = {request.id: request.depends_on for request in requests}
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: str) -> None:
        if node in in_stack:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Batch dependencies contain a cycle.",
            )
        if node in visited:
            return
        in_stack.add(node)
        for child in adjacency[node]:
            _dfs(child)
        in_stack.remove(node)
        visited.add(node)

    for request_id in ids:
        _dfs(request_id)


class BatchService:
    """Execute Graph-style batch requests with per-item isolation."""

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        actor: User,
        principal: AuthenticatedPrincipal,
        rbac: RbacService,
    ) -> None:
        self._session = session
        self._users = UsersService(session=session, settings=settings)
        self._actor = actor
        self._principal = principal
        self._rbac = rbac

    def execute(self, payload: BatchRequest) -> BatchResponse:
        validate_batch_dependencies(payload.requests)

        responses_by_id: dict[str, BatchSubresponse] = {}

        while len(responses_by_id) < len(payload.requests):
            progressed = False
            for request in payload.requests:
                if request.id in responses_by_id:
                    continue

                if any(dependency not in responses_by_id for dependency in request.depends_on):
                    continue

                dependency_failures = [
                    dependency_id
                    for dependency_id in request.depends_on
                    if responses_by_id[dependency_id].status >= status.HTTP_400_BAD_REQUEST
                ]
                if dependency_failures:
                    responses_by_id[request.id] = BatchSubresponse(
                        id=request.id,
                        status=status.HTTP_424_FAILED_DEPENDENCY,
                        body={
                            "detail": (
                                f"Dependency failed for request '{request.id}': "
                                f"{', '.join(dependency_failures)}."
                            )
                        },
                    )
                    progressed = True
                    continue

                responses_by_id[request.id] = self._execute_subrequest(request=request)
                progressed = True

            if not progressed:
                # Defensive fallback: validate_batch_dependencies should prevent this path.
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Unable to resolve batch dependencies.",
                )

        ordered_responses = [responses_by_id[request.id] for request in payload.requests]
        return BatchResponse(responses=ordered_responses)

    def _execute_subrequest(self, *, request: BatchSubrequest) -> BatchSubresponse:
        try:
            operation = parse_batch_operation(method=request.method, url=request.url)
        except HTTPException as exc:
            return _http_exception_response(request_id=request.id, exc=exc)

        if not self._rbac.has_permission(
            principal=self._principal,
            permission_key="users.manage_all",
        ):
            return BatchSubresponse(
                id=request.id,
                status=status.HTTP_403_FORBIDDEN,
                body={"detail": "Global users.manage_all permission required."},
            )

        try:
            with self._session.begin_nested():
                if operation.kind == "create_user":
                    body = request.body if isinstance(request.body, dict) else {}
                    create_payload = UserCreate.model_validate(body)
                    created = self._users.create_user(
                        email=str(create_payload.email),
                        display_name=create_payload.display_name,
                        given_name=create_payload.given_name,
                        surname=create_payload.surname,
                        job_title=create_payload.job_title,
                        department=create_payload.department,
                        office_location=create_payload.office_location,
                        mobile_phone=create_payload.mobile_phone,
                        business_phones=create_payload.business_phones,
                        employee_id=create_payload.employee_id,
                        employee_type=create_payload.employee_type,
                        preferred_language=create_payload.preferred_language,
                        city=create_payload.city,
                        state=create_payload.state,
                        country=create_payload.country,
                        source=create_payload.source,
                        external_id=create_payload.external_id,
                        password_profile=create_payload.password_profile,
                    )
                    assert isinstance(created, UserCreateResponse)
                    created_payload = created.model_dump()
                    location = f"/api/v1/users/{created_payload['user']['id']}"
                    return BatchSubresponse(
                        id=request.id,
                        status=status.HTTP_201_CREATED,
                        headers={"Location": location},
                        body=created_payload,
                    )

                if operation.kind == "update_user":
                    assert operation.user_id is not None
                    body = request.body if isinstance(request.body, dict) else {}
                    update_payload = UserUpdate.model_validate(body)
                    updated = self._users.update_user(
                        user_id=operation.user_id,
                        payload=update_payload,
                        actor=self._actor,
                    )
                    assert isinstance(updated, UserOut)
                    return BatchSubresponse(
                        id=request.id,
                        status=status.HTTP_200_OK,
                        body=updated.model_dump(),
                    )

                assert operation.user_id is not None
                deactivated = self._users.deactivate_user(
                    user_id=operation.user_id,
                    actor=self._actor,
                )
                assert isinstance(deactivated, UserOut)
                return BatchSubresponse(
                    id=request.id,
                    status=status.HTTP_200_OK,
                    body=deactivated.model_dump(),
                )
        except ValidationError as exc:
            return BatchSubresponse(
                id=request.id,
                status=status.HTTP_422_UNPROCESSABLE_CONTENT,
                body={"detail": exc.errors()},
            )
        except HTTPException as exc:
            return _http_exception_response(request_id=request.id, exc=exc)
        except Exception:
            logger.exception(
                "batch.execute_subrequest.unexpected_error",
                extra=log_context(
                    subrequest_id=request.id,
                    method=request.method,
                    url=request.url,
                ),
            )
            return BatchSubresponse(
                id=request.id,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                body={"detail": "Internal server error."},
            )


def _http_exception_response(*, request_id: str, exc: HTTPException) -> BatchSubresponse:
    headers = None
    if isinstance(exc.headers, dict):
        headers = {str(key): str(value) for key, value in exc.headers.items()}
    return BatchSubresponse(
        id=request_id,
        status=int(exc.status_code),
        headers=headers,
        body={"detail": exc.detail},
    )


__all__ = [
    "BatchService",
    "ParsedBatchOperation",
    "parse_batch_operation",
    "validate_batch_dependencies",
]
