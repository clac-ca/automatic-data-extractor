"""Jobs schema placeholders."""

from pydantic import BaseModel


class JobPlaceholder(BaseModel):
    """Placeholder schema for job responses."""

    id: str


__all__ = ["JobPlaceholder"]
