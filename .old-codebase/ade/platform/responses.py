"""Custom response classes built on ADE schema conventions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from starlette.background import BackgroundTask
from starlette.responses import Response

from .schema import BaseSchema

try:  # pragma: no cover - optional dependency
    import orjson  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    orjson = None


class JSONResponse(Response):
    """Response class that understands ADE BaseSchema instances."""

    media_type = "application/json"

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            headers=dict(headers or {}),
            media_type=media_type or self.media_type,
            background=background,
        )
        self.body = self.render(content)

    def render(self, content: Any) -> bytes:  # noqa: D401 - standard Starlette signature
        if content is None:
            return b"null"

        prepared = _prepare_payload(content)
        return _encode_payload(prepared)


class DefaultResponse(BaseSchema):
    """Consistent envelope for success/failure acknowledgements."""

    status: bool
    message: str
    details: dict[str, Any] | None = None

    @classmethod
    def success(
        cls,
        message: str = "OK",
        *,
        details: dict[str, Any] | None = None,
    ) -> DefaultResponse:
        """Return a successful response wrapper."""

        return cls(status=True, message=message, details=details)

    @classmethod
    def failure(
        cls,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> DefaultResponse:
        """Return a failure response wrapper."""

        return cls(status=False, message=message, details=details)


def _prepare_payload(content: Any) -> Any:
    if isinstance(content, BaseSchema):
        return content.serializable_dict()

    if isinstance(content, Mapping):
        return {key: _prepare_payload(value) for key, value in content.items()}

    if isinstance(content, (list, tuple, set)):
        return [_prepare_payload(item) for item in content]

    return content


def _encode_payload(content: Any) -> bytes:
    if orjson is not None:  # pragma: no cover - executed when orjson installed
        return orjson.dumps(content, default=_default_encoder)

    return json.dumps(content, default=_default_encoder, separators=(",", ":")).encode("utf-8")


def _default_encoder(value: Any) -> Any:
    if isinstance(value, BaseSchema):
        return value.serializable_dict()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, set):
        return sorted(_default_encoder(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_default_encoder(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _default_encoder(val) for key, val in value.items()}
    return str(value)


__all__ = ["DefaultResponse", "JSONResponse"]

