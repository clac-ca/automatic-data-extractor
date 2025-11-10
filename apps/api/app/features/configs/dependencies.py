"""Configs dependency placeholders."""

from typing import Any


def get_configs_service() -> Any:
    raise NotImplementedError


def get_configs_repository() -> Any:
    raise NotImplementedError


__all__ = ["get_configs_service", "get_configs_repository"]
