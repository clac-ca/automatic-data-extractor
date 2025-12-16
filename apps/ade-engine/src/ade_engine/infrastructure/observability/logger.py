from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any, TypeAlias

from pydantic import BaseModel, ValidationError

from ade_engine.models.events import (
    CONFIG_NAMESPACE,
    DEFAULT_EVENT,
    ENGINE_EVENT_SCHEMAS,
    ENGINE_NAMESPACE,
)

EventData: TypeAlias = Mapping[str, Any]


def normalize_dotpath(value: str | None) -> str:
    return "" if not value else value.strip().strip(".")


def qualify_event_name(event_name: str, namespace: str) -> str:
    """
    Fully qualify `event_name` under `namespace`.

    - If already under namespace, keep it
    - If it starts with the same root (e.g. "engine.") graft it under namespace
    - Else prefix with namespace
    """
    name = normalize_dotpath(event_name)
    ns = normalize_dotpath(namespace)

    if not ns:
        return name or "invalid_event"
    if not name:
        return f"{ns}.invalid_event"
    if name == ns or name.startswith(f"{ns}."):
        return name

    root = ns.split(".", 1)[0]
    if root and name.startswith(f"{root}."):
        return f"{ns}.{name[len(root) + 1:]}"

    return f"{ns}.{name}"


def _is_engine_event(full_event: str) -> bool:
    return full_event == ENGINE_NAMESPACE or full_event.startswith(f"{ENGINE_NAMESPACE}.")


def _is_config_event(full_event: str) -> bool:
    return full_event == CONFIG_NAMESPACE or full_event.startswith(f"{CONFIG_NAMESPACE}.")


def _validate_payload(full_event: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validate/normalize payload based on policy.

    - Strict: engine.* except engine.config.* must be registered
    - Open:  engine.config.* (validate only if registered)
    - Open:  other namespaces (validate only if registered)
    """
    if _is_engine_event(full_event) and not _is_config_event(full_event):
        if full_event not in ENGINE_EVENT_SCHEMAS:
            raise ValueError(f"Unknown engine event '{full_event}' (add to ENGINE_EVENT_SCHEMAS)")
        schema = ENGINE_EVENT_SCHEMAS[full_event]
    else:
        schema = ENGINE_EVENT_SCHEMAS.get(full_event)  # optional validation

    if schema is None:
        return payload

    try:
        model = schema.model_validate(payload, strict=True)
    except ValidationError as e:
        raise ValueError(f"Invalid payload for event '{full_event}': {e}") from e

    # Keep explicit nulls to preserve schema shape in emitted NDJSON.
    return model.model_dump(mode="python")


class RunLogger(logging.LoggerAdapter):
    """
    LoggerAdapter that:
    - stamps each record with engine_run_id + event_id
    - adds a default event for plain log lines
    - provides .event() for domain events (Pydantic validation for strict engine events)
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        namespace: str = ENGINE_NAMESPACE,
        engine_run_id: str | None = None,
    ) -> None:
        self._namespace = normalize_dotpath(namespace)
        self._engine_run_id = engine_run_id or uuid.uuid4().hex
        super().__init__(logger, {"namespace": self._namespace, "engine_run_id": self._engine_run_id})

    @property
    def namespace(self) -> str:
        return str((self.extra or {}).get("namespace", ""))

    @property
    def engine_run_id(self) -> str:
        return self._engine_run_id

    def with_namespace(self, namespace: str) -> "RunLogger":
        return RunLogger(self.logger, namespace=namespace, engine_run_id=self._engine_run_id)

    def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        caller_extra = kwargs.pop("extra", None)
        extra = dict(self.extra or {})

        if caller_extra is not None:
            if not isinstance(caller_extra, Mapping):
                raise TypeError("logging 'extra' must be a mapping")
            extra.update(caller_extra)

        # Stable run id (caller can't override).
        extra["engine_run_id"] = self._engine_run_id

        # Normalize namespace.
        ns = normalize_dotpath(str(extra.get("namespace") or ""))
        if ns:
            extra["namespace"] = ns
        else:
            extra.pop("namespace", None)

        # Per-record id.
        extra["event_id"] = str(extra.get("event_id") or uuid.uuid4().hex)

        # Default event for plain log lines.
        extra.setdefault("event", qualify_event_name(DEFAULT_EVENT, ns) if ns else DEFAULT_EVENT)

        # Normalize `data`.
        data = extra.get("data")
        if data is not None and not isinstance(data, Mapping):
            extra["data"] = {"value": data}

        kwargs["extra"] = extra
        return msg, kwargs

    def event(
        self,
        name: str,
        *,
        message: str | None = None,
        level: int = logging.INFO,
        data: EventData | None = None,
        exc: BaseException | None = None,
        **fields: Any,
    ) -> None:
        if not self.isEnabledFor(level):
            return

        ns = self.namespace
        full_name = qualify_event_name(name, ns) if ns else normalize_dotpath(name) or "invalid_event"

        payload: dict[str, Any] = {}
        if data:
            payload.update(dict(data))
        if fields:
            payload.update(fields)

        payload = _validate_payload(full_name, payload)

        extra: dict[str, Any] = {"event": full_name}
        if payload:
            extra["data"] = payload

        exc_info = (type(exc), exc, exc.__traceback__) if exc is not None else None
        self.log(level, message or full_name, extra=extra, exc_info=exc_info)


class NullLogger(RunLogger):
    """A RunLogger implementation that discards all log/event output."""

    def __init__(
        self,
        *,
        namespace: str = ENGINE_NAMESPACE,
        engine_run_id: str = "null",
    ) -> None:
        base_logger = logging.Logger("ade_engine.null")
        base_logger.addHandler(logging.NullHandler())
        base_logger.propagate = False
        base_logger.disabled = True
        super().__init__(base_logger, namespace=namespace, engine_run_id=engine_run_id)

    def with_namespace(self, namespace: str) -> "NullLogger":
        return NullLogger(namespace=namespace, engine_run_id=self._engine_run_id)

    def __bool__(self) -> bool:
        return False


__all__ = [
    "RunLogger",
    "NullLogger",
    "normalize_dotpath",
    "qualify_event_name",
]
