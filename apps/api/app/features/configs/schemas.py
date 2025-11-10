"""Configs schema placeholders."""

from pydantic import BaseModel


class ConfigPlaceholder(BaseModel):
    """Placeholder schema for future config responses."""

    id: str


__all__ = ["ConfigPlaceholder"]
