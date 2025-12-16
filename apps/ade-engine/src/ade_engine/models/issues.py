from __future__ import annotations

from typing import Any, Iterable

from ade_engine.models.errors import PipelineError

Issue = dict[str, Any]
IssueCell = Issue | list[Issue] | None

IssuesPatch = dict[str, list[IssueCell]]

_ALLOWED_SEVERITIES = {"info", "warning", "error"}


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


def normalize_issue_cell(*, raw: Any, source: str) -> IssueCell:
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


def merge_issue_cell(existing: IssueCell, new: IssueCell) -> IssueCell:
    return _merge_issue_cells(existing, new)


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


def ensure_registered_fields(
    *,
    fields: Iterable[str],
    registry_fields: set[str],
    source: str,
) -> None:
    unknown = sorted({f for f in fields if f not in registry_fields})
    if unknown:
        unknown_str = ", ".join(unknown)
        raise PipelineError(f"{source} emitted unknown field(s): {unknown_str}")


__all__ = [
    "Issue",
    "IssueCell",
    "IssuesPatch",
    "ensure_registered_fields",
    "merge_issue_cell",
    "merge_issues_patch",
    "normalize_issue_cell",
]
