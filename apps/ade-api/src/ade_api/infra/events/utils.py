from __future__ import annotations

from typing import Any

from ade_api.schemas.events import AdeEvent


class PayloadDict(dict[str, Any]):
    """Dict wrapper that also exposes keys via attribute access."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(key) from exc


def ensure_event_defaults(event: AdeEvent, *, default_source: str = "api") -> AdeEvent:
    """Populate common defaults and payload helpers on ``event`` in-place."""

    if getattr(event, "source", None) is None:
        event.source = default_source

    payload = getattr(event, "payload", None)
    if isinstance(payload, dict) and not isinstance(payload, PayloadDict):
        event.payload = PayloadDict(payload)

    return event


__all__ = ["PayloadDict", "ensure_event_defaults"]
