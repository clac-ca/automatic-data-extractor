from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ade_engine.exceptions import PipelineError

Issue = dict[str, Any]
IssueCell = Issue | list[Issue] | None

ValuesPatch = dict[str, list[Any]]
IssuesPatch = dict[str, list[IssueCell]]

_ALLOWED_SEVERITIES = {"info", "warning", "error"}
_ENVELOPE_KEYS = {"values", "issues", "meta"}


@dataclass(frozen=True)
class TablePatch:
    values: ValuesPatch = field(default_factory=dict)
    issues: IssuesPatch = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def _ensure_registered_fields(
    *,
    fields: Iterable[str],
    registry_fields: set[str],
    source: str,
) -> None:
    unknown = sorted({f for f in fields if f not in registry_fields})
    if unknown:
        unknown_str = ", ".join(unknown)
        raise PipelineError(f"{source} emitted unknown field(s): {unknown_str}")


def _validate_column_vec(*, vec: Any, row_count: int, source: str) -> list[Any]:
    if not isinstance(vec, list):
        raise PipelineError(f"{source} must be a list (got {type(vec).__name__})")
    if len(vec) != row_count:
        raise PipelineError(f"{source} must have length {row_count} (got {len(vec)})")
    return vec


def _validate_issue(*, raw: Any, source: str) -> Issue:
    if not isinstance(raw, dict):
        raise PipelineError(f"{source} must be a dict (got {type(raw).__name__})")

    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        raise PipelineError(f"{source} must include a non-empty 'message'")

    severity = raw.get("severity")
    if severity is not None:
        if not isinstance(severity, str):
            raise PipelineError(f"{source} 'severity' must be a string or None")
        if severity not in _ALLOWED_SEVERITIES:
            allowed = ", ".join(sorted(_ALLOWED_SEVERITIES))
            raise PipelineError(f"{source} 'severity' must be one of: {allowed}")

    code = raw.get("code")
    if code is not None and not isinstance(code, str):
        raise PipelineError(f"{source} 'code' must be a string or None")

    meta = raw.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise PipelineError(f"{source} 'meta' must be a dict or None")

    return raw


def _normalize_issue_cell(*, raw: Any, source: str) -> IssueCell:
    if raw is None:
        return None
    if isinstance(raw, list):
        normalized: list[Issue] = []
        for idx, item in enumerate(raw):
            normalized.append(_validate_issue(raw=item, source=f"{source}[{idx}]"))
        return normalized
    return _validate_issue(raw=raw, source=source)


def _merge_issue_cells(existing: IssueCell, new: IssueCell) -> IssueCell:
    if new is None:
        return existing
    if existing is None:
        return new
    if isinstance(existing, list):
        if isinstance(new, list):
            return [*existing, *new]
        return [*existing, new]
    if isinstance(new, list):
        return [existing, *new]
    return [existing, new]


def merge_issues_patch(target: IssuesPatch, patch: IssuesPatch) -> None:
    for field, vec in patch.items():
        if field not in target:
            target[field] = vec
            continue
        out = target[field]
        if len(out) != len(vec):
            raise PipelineError(
                f"Cannot merge issues for '{field}': length mismatch ({len(out)} vs {len(vec)})"
            )
        for idx, cell in enumerate(vec):
            out[idx] = _merge_issue_cells(out[idx], cell)


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
        _ensure_registered_fields(fields=[field_name], registry_fields=registry_fields, source=source)
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
            values[key] = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} values['{key}']")
        _ensure_registered_fields(fields=values.keys(), registry_fields=registry_fields, source=source)

        issues: IssuesPatch = {}
        for key, vec in issues_raw.items():
            if not isinstance(key, str):
                raise PipelineError(f"{source} 'issues' keys must be strings")
            vec_list = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} issues['{key}']")
            issues[key] = [
                _normalize_issue_cell(raw=cell, source=f"{source} issues['{key}'][{idx}]")
                for idx, cell in enumerate(vec_list)
            ]
        _ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)

        return TablePatch(values=values, issues=issues, meta=meta_raw)

    # Values patch (multi-output)
    values = {}
    for key, vec in raw.items():
        if not isinstance(key, str):
            raise PipelineError(f"{source} patch keys must be strings")
        values[key] = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} patch['{key}']")
    _ensure_registered_fields(fields=values.keys(), registry_fields=registry_fields, source=source)
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

            _ensure_registered_fields(fields=[issue_field], registry_fields=registry_fields, source=source)
            issue = _validate_issue(raw=item, source=f"{source} issue[{idx}]")

            vec = issues.setdefault(issue_field, [None] * row_count)
            vec[row_index] = _merge_issue_cells(vec[row_index], issue)

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
                _normalize_issue_cell(raw=cell, source=f"{source} issues['{key}'][{idx}]")
                for idx, cell in enumerate(vec_list)
            ]
        _ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)
        return TablePatch(issues=issues, meta=meta_raw)

    # Issue patch vectors
    issues: IssuesPatch = {}
    for key, vec in raw.items():
        if not isinstance(key, str):
            raise PipelineError(f"{source} issue patch keys must be strings")
        vec_list = _validate_column_vec(vec=vec, row_count=row_count, source=f"{source} patch['{key}']")
        issues[key] = [
            _normalize_issue_cell(raw=cell, source=f"{source} patch['{key}'][{idx}]")
            for idx, cell in enumerate(vec_list)
        ]
    _ensure_registered_fields(fields=issues.keys(), registry_fields=registry_fields, source=source)
    return TablePatch(issues=issues)


__all__ = [
    "Issue",
    "IssueCell",
    "IssuesPatch",
    "TablePatch",
    "ValuesPatch",
    "merge_issues_patch",
    "normalize_transform_return",
    "normalize_validator_return",
]

