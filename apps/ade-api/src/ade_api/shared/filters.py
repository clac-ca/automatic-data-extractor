from __future__ import annotations

from ade_api.shared.core.schema import BaseSchema


class FilterBase(BaseSchema):
    """Base model for query filter payloads.

    Unknown query parameters are rejected to surface typos quickly.
    """


__all__ = ["FilterBase"]
