"""Jobs dependency placeholders."""

from typing import Any


def get_jobs_service() -> Any:
    raise NotImplementedError


def get_jobs_repository() -> Any:
    raise NotImplementedError


__all__ = ["get_jobs_service", "get_jobs_repository"]
