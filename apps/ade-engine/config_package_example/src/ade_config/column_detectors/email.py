from __future__ import annotations

import re
from typing import Any, Dict

from ade_engine.registry.models import FieldDef

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register(registry):
    registry.register_field(FieldDef(name="email", dtype="string"))
    registry.register_column_detector(detect_email_header, field="email", priority=60)
    registry.register_column_detector(detect_email_values, field="email", priority=30)
    registry.register_column_transform(normalize_email, field="email", priority=0)
    registry.register_column_validator(validate_email, field="email", priority=0)
    # If you prefer per-cell helpers, uncomment the functions below and register them instead:
    # registry.register_cell_transform(normalize_email_cell, field="email", priority=0)
    # registry.register_cell_validator(validate_email_cell, field="email", priority=0)


def detect_email_header(
    *,
    column_index,
    header,
    values,
    values_sample,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    header = "" if header is None else str(header).strip().lower()
    if not header:
        return None
    if "email" in header or "e-mail" in header:
        return {"email": 1.0}
    return None


def detect_email_values(
    *,
    column_index,
    header,
    values,
    values_sample,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    values_sample = values_sample or []
    hits = 0
    total = 0
    for v in values_sample:
        s = _norm(v)
        if not s:
            continue
        total += 1
        if EMAIL_RE.match(s):
            hits += 1
    if total == 0:
        return None
    score = min(1.0, hits / total)
    return {"email": score}


def normalize_email(*, field_name, values, mapping, state, metadata, input_file_name, logger) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "value": {"email": ...}}, ...]`."""

    return [
        {
            "row_index": idx,
            "value": {
                "email": (_norm(v) or None),
            },
        }
        for idx, v in enumerate(values)
    ]


def validate_email(*, field_name, values, mapping, state, metadata, column_index, input_file_name, logger) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "message": str}, ...]` for invalid cells."""

    issues: list[Dict[str, Any]] = []
    for idx, v in enumerate(values):
        s = _norm(v)
        if not s:
            continue
        if not EMAIL_RE.match(s):
            issues.append({
                "row_index": idx,
                "message": f"Invalid email: {v}",
            })
    return issues

# Optional cell-level helpers (commented out):
# - These are thin wrappers that handle one cell at a time.
# - Use the column-level versions above for better performance or when emitting multiple fields per column.
#
# def normalize_email_cell(value: object | None) -> Dict[str, Any]:
#     """Return a single normalized email dict for one cell."""
#     return {"row_index": 0, "value": {"email": (_norm(value) or None)}}
#
# def validate_email_cell(value: object | None) -> Dict[str, Any] | None:
#     """Validate one email cell; return a single issue or None."""
#     text_value = _norm(value)
#     if text_value and not EMAIL_RE.match(text_value):
#         return {"row_index": 0, "message": f"Invalid email: {value}"}
#     return None
