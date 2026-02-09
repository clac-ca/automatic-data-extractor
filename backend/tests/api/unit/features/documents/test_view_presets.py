from __future__ import annotations

from uuid import UUID, uuid4

from ade_api.features.documents.view_presets import (
    SYSTEM_DOCUMENT_VIEW_PRESETS,
    is_system_view_id,
    preset_by_view_id,
    reserved_system_name_keys,
    system_view_id,
)


def test_system_view_ids_are_deterministic_and_unique() -> None:
    workspace_id = UUID("11111111-2222-3333-4444-555555555555")
    first = [
        system_view_id(workspace_id=workspace_id, system_key=preset.system_key)
        for preset in SYSTEM_DOCUMENT_VIEW_PRESETS
    ]
    second = [
        system_view_id(workspace_id=workspace_id, system_key=preset.system_key)
        for preset in SYSTEM_DOCUMENT_VIEW_PRESETS
    ]

    assert first == second
    assert len(first) == len(set(first))


def test_preset_lookup_by_view_id() -> None:
    workspace_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    for preset in SYSTEM_DOCUMENT_VIEW_PRESETS:
        view_id = system_view_id(workspace_id=workspace_id, system_key=preset.system_key)
        resolved = preset_by_view_id(workspace_id=workspace_id, view_id=view_id)
        assert resolved is not None
        assert resolved.system_key == preset.system_key
        assert is_system_view_id(workspace_id=workspace_id, view_id=view_id)

    unknown = uuid4()
    assert preset_by_view_id(workspace_id=workspace_id, view_id=unknown) is None
    assert not is_system_view_id(workspace_id=workspace_id, view_id=unknown)


def test_reserved_name_keys_match_presets() -> None:
    expected = {preset.name_key for preset in SYSTEM_DOCUMENT_VIEW_PRESETS}
    assert reserved_system_name_keys() == expected
