from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ade_engine.models.errors import PipelineError
from ade_engine.models.issues import (
    IssuesPatch,
    ensure_registered_fields,
    merge_issue_cell,
    normalize_issue_cell,
)

ValuesPatch = dict[str, list[Any]]

_ENVELOPE_KEYS = {"values", "issues", "meta"}


@dataclass(frozen=True)
class TablePatch:
    values: ValuesPatch = field(default_factory=dict)
    issues: IssuesPatch = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def _validate_column_vec(*, vec: Any, row_count: int, source: str) -> list[Any]:
    if not isinstance(vec, list):
        raise PipelineError(f"{source} must be a list (got {type(vec).__name__})")
    if len(vec) != row_count:
        raise PipelineError(f"{source} must have length {row_count} (got {len(vec)})")
    return vec


def normalize_transform_return(
    *,
    field_name: str,
    raw: Any,
    row_count: int,
    registry_fields: set[str],
    source: str,
) -> TablePatch:
    if raw is None:
        return TablePatch()

    if isinstance(raw, list):
        vec = _validate_column_vec(vec=raw, row_count=row_count, source=source)
        ensure_registered_fields(fields=[field_name], registry_fields=registry_fields, source=source)
        return TablePatch(values={field_name: vec})

    if not isinstance(raw, dict):
        raise PipelineError(f"{source} must return None, a list, a dict[str, list], or a TablePatch envelope")

    # TablePatch envelope
    if set(raw).issubset(_ENVELOPE_KEYS) and ("values" in raw or "issues" in raw or "meta" in raw):
        values_raw = raw.get("values") or {}
        issues_raw = raw.get("issues") or {}
        meta_raw = raw.get("meta") or {}

        if not isinstance(values_raw, dict):
            raise PipelineError(f"{source} 'values' must be a dict[str, list]")
        if not isinstance(issues_raw, dict):
            raise PipelineError(f"{source} 'issues' must be a dict[str, list]")
        if not isinstance(meta_raw, dict):
            raise PipelineError(f"{source} 'meta' must be a dict")

        values: ValuesPatch = {}
        for key, vec in values_raw.items():
            if not isinstance(key, str):
                raise PipelineError(f"{source} 'values' keys must be strings")
            values[key] = _validate_column_vec(
                vec=vec, row_count=row_count, source=f"{source} values['{key}']"
            )
        ensure_registered_fields(fields=values.keys(), registry_fields=registry_fields, source=source)

        issues: IssuesPatch = {}
        for key, vec in issues_raw.items():
            if not isinstance(key, str):
                raise PipelineError(f"{source} 'issues' keys must be strings")
            vec_list = _validate_column_vec(
                vec=vec, row_count=row_count, source=f"{source} issues['{key}']"
            )
            issues[key] = [
                normalize_issue_cell(raw=cell, source=f"{source} issues['{key}'][{idx}]")
                for idx, cell in enumerate(vec_list)
            ]
        ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)

        return TablePatch(values=values, issues=issues, meta=meta_raw)

    # Values patch (multi-output)
    values = {}
    for key, vec in raw.items():
        if not isinstance(key, str):
            raise PipelineError(f"{source} patch keys must be strings")
        values[key] = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} patch['{key}']")
    ensure_registered_fields(fields=values.keys(), registry_fields=registry_fields, source=source)
    return TablePatch(values=values)


def normalize_validator_return(
    *,
    field_name: str,
    raw: Any,
    row_count: int,
    registry_fields: set[str],
    source: str,
) -> TablePatch:
    if raw is None or raw == []:
        return TablePatch()

    # Sparse issue list
    if isinstance(raw, list):
        issues: IssuesPatch = {}
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                raise PipelineError(f"{source} issues must be dicts (got {type(item).__name__} at {idx})")
            row_index = item.get("row_index")
            if isinstance(row_index, bool) or not isinstance(row_index, int):
                raise PipelineError(f"{source} issue.row_index must be an integer (at {idx})")
            if not (0 <= row_index < row_count):
                raise PipelineError(f"{source} issue.row_index out of range (at {idx})")

            issue_field = item.get("field", field_name)
            if not isinstance(issue_field, str) or not issue_field:
                raise PipelineError(f"{source} issue.field must be a non-empty string (at {idx})")

            ensure_registered_fields(fields=[issue_field], registry_fields=registry_fields, source=source)

            vec = issues.setdefault(issue_field, [None] * row_count)
            vec[row_index] = merge_issue_cell(
                vec[row_index],
                normalize_issue_cell(raw=item, source=f"{source} issue[{idx}]"),
            )

        return TablePatch(issues=issues)

    if not isinstance(raw, dict):
        raise PipelineError(f"{source} must return None, a list, a dict[str, issue_vector], or a TablePatch envelope")

    # TablePatch envelope
    if set(raw).issubset(_ENVELOPE_KEYS) and ("issues" in raw or "meta" in raw or "values" in raw):
        if "values" in raw and raw.get("values") not in (None, {}, []):
            raise PipelineError(f"{source} validators must not return 'values'")

        issues_raw = raw.get("issues") or {}
        meta_raw = raw.get("meta") or {}

        if not isinstance(issues_raw, dict):
            raise PipelineError(f"{source} 'issues' must be a dict[str, list]")
        if not isinstance(meta_raw, dict):
            raise PipelineError(f"{source} 'meta' must be a dict")

        issues: IssuesPatch = {}
        for key, vec in issues_raw.items():
            if not isinstance(key, str):
                raise PipelineError(f"{source} 'issues' keys must be strings")
            vec_list = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} issues['{key}']")
            issues[key] = [
                normalize_issue_cell(raw=cell, source=f"{source} issues['{key}'][{idx}]")
                for idx, cell in enumerate(vec_list)
            ]
        ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)
        return TablePatch(issues=issues, meta=meta_raw)

    # Issue patch vectors
    issues: IssuesPatch = {}
    for key, vec in raw.items():
        if not isinstance(key, str):
            raise PipelineError(f"{source} issue patch keys must be strings")
        vec_list = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} patch['{key}']")
        issues[key] = [
            normalize_issue_cell(raw=cell, source=f"{source} patch['{key}'][{idx}]")
            for idx, cell in enumerate(vec_list)
        ]
    ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)
    return TablePatch(issues=issues)


__all__ = [
    "TablePatch",
    "ValuesPatch",
    "normalize_transform_return",
    "normalize_validator_return",
]
