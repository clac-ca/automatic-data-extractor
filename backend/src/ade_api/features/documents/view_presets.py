"""Immutable virtual presets for document list system views."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

SYSTEM_VIEW_ID_NAMESPACE = UUID("2da5b95a-2ac7-4f5c-982b-b3e13d6f65f1")


@dataclass(frozen=True, slots=True)
class SystemDocumentViewPreset:
    """Definition for a virtual system document view."""

    system_key: str
    name: str
    name_key: str
    query_state: dict[str, object]


SYSTEM_DOCUMENT_VIEW_PRESETS: tuple[SystemDocumentViewPreset, ...] = (
    SystemDocumentViewPreset(
        system_key="all_documents",
        name="All documents",
        name_key="all-documents",
        query_state={
            "lifecycle": "active",
            "q": None,
            "sort": [{"id": "createdAt", "desc": True}],
            "filters": [],
            "joinOperator": "and",
        },
    ),
    SystemDocumentViewPreset(
        system_key="assigned_to_me",
        name="Assigned to me",
        name_key="assigned-to-me",
        query_state={
            "lifecycle": "active",
            "q": None,
            "sort": [{"id": "createdAt", "desc": True}],
            "filters": [
                {
                    "id": "assigneeId",
                    "operator": "inArray",
                    "value": ["me"],
                    "variant": "multiSelect",
                    "filterId": "system-assigned-to-me",
                }
            ],
            "joinOperator": "and",
        },
    ),
    SystemDocumentViewPreset(
        system_key="unassigned",
        name="Unassigned",
        name_key="unassigned",
        query_state={
            "lifecycle": "active",
            "q": None,
            "sort": [{"id": "createdAt", "desc": True}],
            "filters": [
                {
                    "id": "assigneeId",
                    "operator": "isEmpty",
                    "value": "",
                    "variant": "multiSelect",
                    "filterId": "system-unassigned",
                }
            ],
            "joinOperator": "and",
        },
    ),
    SystemDocumentViewPreset(
        system_key="deleted",
        name="Deleted",
        name_key="deleted",
        query_state={
            "lifecycle": "deleted",
            "q": None,
            "sort": [{"id": "deletedAt", "desc": True}],
            "filters": [],
            "joinOperator": "and",
        },
    ),
)

_PRESET_BY_SYSTEM_KEY: dict[str, SystemDocumentViewPreset] = {
    preset.system_key: preset for preset in SYSTEM_DOCUMENT_VIEW_PRESETS
}


def system_view_id(*, workspace_id: UUID, system_key: str) -> UUID:
    """Return deterministic UUIDv5 for a virtual system view."""

    return uuid5(SYSTEM_VIEW_ID_NAMESPACE, f"{workspace_id}:{system_key}")


def preset_by_view_id(*, workspace_id: UUID, view_id: UUID) -> SystemDocumentViewPreset | None:
    """Resolve a virtual system preset by its deterministic view id."""

    for preset in SYSTEM_DOCUMENT_VIEW_PRESETS:
        if system_view_id(workspace_id=workspace_id, system_key=preset.system_key) == view_id:
            return preset
    return None


def is_system_view_id(*, workspace_id: UUID, view_id: UUID) -> bool:
    """Return whether ``view_id`` resolves to a virtual system view."""

    return preset_by_view_id(workspace_id=workspace_id, view_id=view_id) is not None


def reserved_system_name_keys() -> frozenset[str]:
    """Return reserved slug keys for system view names."""

    return frozenset(preset.name_key for preset in SYSTEM_DOCUMENT_VIEW_PRESETS)


def preset_by_system_key(system_key: str) -> SystemDocumentViewPreset | None:
    """Return a system preset by key."""

    return _PRESET_BY_SYSTEM_KEY.get(system_key)


__all__ = [
    "SYSTEM_DOCUMENT_VIEW_PRESETS",
    "SYSTEM_VIEW_ID_NAMESPACE",
    "SystemDocumentViewPreset",
    "is_system_view_id",
    "preset_by_system_key",
    "preset_by_view_id",
    "reserved_system_name_keys",
    "system_view_id",
]
