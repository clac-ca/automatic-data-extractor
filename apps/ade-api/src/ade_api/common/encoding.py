"""Shared JSON encoding helpers with consistent UUID handling."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

try:  # pragma: no cover - optional dependency
    import orjson  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    orjson = None


def json_default_encoder(value: Any) -> Any:
    """Best-effort serializer that handles ADE primitives and UUIDs."""

    # Local import avoids circular dependency at module import time.
    from ade_api.common.schema import BaseSchema

    if isinstance(value, BaseSchema):
        return value.serializable_dict()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, set):
        return sorted(json_default_encoder(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [json_default_encoder(item) for item in value]
    return str(value)


def _normalize_json(content: Any) -> Any:
    """Normalize structures so keys are JSON-friendly before encoding."""

    # Local import avoids circular dependency at module import time.
    from ade_api.common.schema import BaseSchema

    if isinstance(content, BaseSchema):
        return content.serializable_dict()
    if isinstance(content, Mapping):
        return {str(key): _normalize_json(val) for key, val in content.items()}
    if isinstance(content, (list, tuple, set)):
        return [_normalize_json(item) for item in content]
    return content


def json_dumps(
    content: Any,
    *,
    indent: int | None = None,
    separators: tuple[str, str] | None = (",", ":"),
    sort_keys: bool | None = False,
) -> str:
    """Render JSON using the shared encoder."""

    normalized = _normalize_json(content)
    if orjson is not None and indent is None:  # pragma: no cover - optional dependency path
        options = 0
        if sort_keys:
            options |= getattr(orjson, "OPT_SORT_KEYS", 0)
        return orjson.dumps(normalized, default=json_default_encoder, option=options).decode("utf-8")

    kwargs: dict[str, Any] = {"default": json_default_encoder}
    if indent is not None:
        kwargs["indent"] = indent
    if separators is not None:
        kwargs["separators"] = separators
    if sort_keys is not None:
        kwargs["sort_keys"] = sort_keys
    return json.dumps(normalized, **kwargs)


def json_bytes(
    content: Any,
    *,
    indent: int | None = None,
    separators: tuple[str, str] | None = (",", ":"),
    sort_keys: bool | None = False,
) -> bytes:
    """Render JSON bytes using the shared encoder."""

    return json_dumps(content, indent=indent, separators=separators, sort_keys=sort_keys).encode(
        "utf-8"
    )


__all__ = ["json_default_encoder", "json_dumps", "json_bytes"]
