"""Row normalization and validation."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import ColumnMapping, ColumnModule, ExtraColumn


def normalize_rows(
    job: JobContext,
    rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    mapping: Sequence[ColumnMapping],
    extras: Sequence[ExtraColumn],
    modules: Mapping[str, ColumnModule],
    meta: Mapping[str, Mapping[str, Any]],
    *,
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> tuple[list[list[Any]], list[dict[str, Any]]]:
    """Apply transforms and validators to produce normalized rows."""

    index_by_field = {entry.field: entry.index for entry in mapping}
    normalized: list[list[Any]] = []
    issues: list[dict[str, Any]] = []
    active_modules = {field: module for field, module in modules.items() if field in order}

    for zero_index, row in enumerate(rows):
        row_index = zero_index + 2  # header row is index 1
        canonical_row: dict[str, Any] = {}
        for field in order:
            idx = index_by_field.get(field)
            value = row[idx] if idx is not None and idx < len(row) else None
            canonical_row[field] = value

        for field in order:
            module = active_modules.get(field)
            if module is None or module.transformer is None:
                continue
            value = canonical_row.get(field)
            try:
                updates = module.transformer(
                    job=job,
                    state=state,
                    row_index=row_index,
                    field_name=field,
                    value=value,
                    row=canonical_row,
                    field_meta=meta.get(field),
                    logger=logger,
                )
            except Exception as exc:  # pragma: no cover - transform failure
                raise RuntimeError(
                    f"Transform for field '{field}' failed on row {row_index}: {exc}"
                ) from exc
            if updates:
                canonical_row.update(dict(updates))

        for field in order:
            module = active_modules.get(field)
            if module is None or module.validator is None:
                continue
            value = canonical_row.get(field)
            field_meta = meta.get(field)
            try:
                results = module.validator(
                    job=job,
                    state=state,
                    row_index=row_index,
                    field_name=field,
                    value=value,
                    row=canonical_row,
                    field_meta=field_meta,
                    logger=logger,
                )
            except Exception as exc:  # pragma: no cover - validation failure
                raise RuntimeError(
                    f"Validator for field '{field}' failed on row {row_index}: {exc}"
                ) from exc
            for issue in results or []:
                payload = dict(issue)
                payload.setdefault("row_index", row_index)
                payload.setdefault("field", field)
                issues.append(payload)

        normalized_row = [canonical_row.get(field) for field in order]
        for extra in extras:
            value = row[extra.index] if extra.index < len(row) else None
            normalized_row.append(value)
        normalized.append(normalized_row)

    return normalized, issues


__all__ = ["normalize_rows"]
