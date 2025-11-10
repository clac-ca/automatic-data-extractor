"""Configs model placeholders."""

from sqlalchemy.orm import Mapped


class Config:  # pragma: no cover - stub
    """Placeholder ORM model for configs."""

    id: Mapped[str]


class ConfigVersion:  # pragma: no cover - stub
    """Placeholder ORM model for config versions."""

    id: Mapped[str]


__all__ = ["Config", "ConfigVersion"]
