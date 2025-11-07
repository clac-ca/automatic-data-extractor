from __future__ import annotations

from pydantic import BaseModel


class FilterBase(BaseModel):
    """Base model for query filter payloads.

    Unknown query parameters are rejected to surface typos quickly.
    """

    model_config = {"extra": "forbid"}


__all__ = ["FilterBase"]
