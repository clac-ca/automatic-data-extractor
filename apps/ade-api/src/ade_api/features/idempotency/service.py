"""Idempotency key handling for replayable POST responses."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import status
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.problem_details import ApiError, ProblemDetailsErrorItem
from ade_api.common.time import utc_now
from ade_api.models import IdempotencyRecord
from ade_api.settings import Settings

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
MAX_IDEMPOTENCY_KEY_LENGTH = 128


@dataclass(frozen=True)
class IdempotencyReplay:
    """Response payload recorded for an idempotent request."""

    status_code: int
    headers: dict[str, str]
    body: Any | None

    def to_response(self) -> Response:
        if self.body is None:
            return Response(status_code=self.status_code, headers=self.headers)
        return JSONResponse(status_code=self.status_code, content=self.body, headers=self.headers)


def normalize_idempotency_key(raw: str | None) -> str:
    """Validate and normalize the Idempotency-Key header."""

    if raw is None or not str(raw).strip():
        raise ApiError(
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key header is required.",
            errors=[
                ProblemDetailsErrorItem(
                    path=IDEMPOTENCY_KEY_HEADER,
                    message="Missing Idempotency-Key header.",
                    code="required",
                )
            ],
        )

    value = str(raw).strip()
    if len(value) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ApiError(
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key exceeds maximum length.",
            errors=[
                ProblemDetailsErrorItem(
                    path=IDEMPOTENCY_KEY_HEADER,
                    message="Idempotency-Key is too long.",
                    code="max_length",
                )
            ],
        )
    return value


def build_scope_key(*, principal_id: str, workspace_id: str | None = None) -> str:
    """Build a stable scope key for idempotency tracking."""

    if workspace_id:
        return f"workspace:{workspace_id}:user:{principal_id}"
    return f"user:{principal_id}"


def build_request_hash(*, method: str, path: str, payload: Any | None) -> str:
    """Hash method + path + payload for idempotency comparisons."""

    canonical = json.dumps(
        {
            "method": method.upper(),
            "path": path,
            "payload": jsonable_encoder(payload, by_alias=True, exclude_none=True),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sanitize_headers(headers: Mapping[str, str] | None) -> dict[str, str] | None:
    if not headers:
        return None

    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if value is None:
            continue
        normalized = str(key)
        if normalized.lower() in {"content-length", "x-request-id", "x-response-time-ms"}:
            continue
        sanitized[normalized] = str(value)

    return sanitized or None


class IdempotencyService:
    """Persist and replay idempotent request/response pairs."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._ttl = settings.idempotency_key_ttl

    async def resolve_replay(
        self,
        *,
        key: str,
        scope_key: str,
        request_hash: str,
    ) -> IdempotencyReplay | None:
        record = await self._get_record(key=key, scope_key=scope_key)
        if record is None:
            return None

        now = utc_now()
        if record.expires_at <= now:
            await self._session.delete(record)
            await self._session.flush()
            return None

        if record.request_hash != request_hash:
            raise ApiError(
                error_type="idempotency_key_conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key has already been used for a different request.",
                errors=[
                    ProblemDetailsErrorItem(
                        path=IDEMPOTENCY_KEY_HEADER,
                        message="Idempotency-Key does not match the original request.",
                        code="idempotency_key_conflict",
                    )
                ],
            )

        return IdempotencyReplay(
            status_code=record.response_status,
            headers=record.response_headers or {},
            body=record.response_body,
        )

    async def store_response(
        self,
        *,
        key: str,
        scope_key: str,
        request_hash: str,
        status_code: int,
        body: Any | None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        record = IdempotencyRecord(
            idempotency_key=key,
            scope_key=scope_key,
            request_hash=request_hash,
            response_status=status_code,
            response_headers=_sanitize_headers(headers),
            response_body=jsonable_encoder(body, by_alias=True, exclude_none=True),
            expires_at=utc_now() + self._ttl,
        )

        async with self._session.begin_nested():
            self._session.add(record)
            try:
                await self._session.flush()
            except IntegrityError:
                return

    async def _get_record(self, *, key: str, scope_key: str) -> IdempotencyRecord | None:
        stmt = (
            select(IdempotencyRecord)
            .where(IdempotencyRecord.idempotency_key == key)
            .where(IdempotencyRecord.scope_key == scope_key)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = [
    "IDEMPOTENCY_KEY_HEADER",
    "IdempotencyReplay",
    "IdempotencyService",
    "MAX_IDEMPOTENCY_KEY_LENGTH",
    "build_request_hash",
    "build_scope_key",
    "normalize_idempotency_key",
]
