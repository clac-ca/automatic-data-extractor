"""Jobs schema placeholders."""

from apps.api.app.shared.core.schema import BaseSchema


class JobPlaceholder(BaseSchema):
    """Placeholder schema for job responses."""

    id: str


__all__ = ["JobPlaceholder"]
