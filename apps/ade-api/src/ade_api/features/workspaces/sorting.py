from __future__ import annotations

from .schemas import WorkspaceMemberOut, WorkspaceOut


def _lower(value: str | None) -> str:
    return (value or "").lower()


SORT_FIELDS = {
    "name": lambda item: _lower(item.name),
    "slug": lambda item: _lower(item.slug),
    "isDefault": lambda item: item.is_default,
    "processingPaused": lambda item: item.processing_paused,
}

DEFAULT_SORT = ["name"]


def id_key(item: WorkspaceOut) -> str:
    return str(item.id)


MEMBER_SORT_FIELDS = {
    "userId": lambda item: str(item.user_id),
    "createdAt": lambda item: item.created_at,
}

MEMBER_DEFAULT_SORT = ["userId"]


def member_id_key(item: WorkspaceMemberOut) -> str:
    return str(item.user_id)


__all__ = [
    "DEFAULT_SORT",
    "MEMBER_DEFAULT_SORT",
    "MEMBER_SORT_FIELDS",
    "SORT_FIELDS",
    "id_key",
    "member_id_key",
]
