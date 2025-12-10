from __future__ import annotations

import re

from ade_engine.registry.models import ColumnDetectorContext, FieldDef, TransformContext, ValidateContext

from ade_config.column_detectors.types import ColumnTransformRow, ColumnValidatorIssue, ScoreMap

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register(registry):
    registry.register_field(FieldDef(
        name="email",
        label="Email",
        required=True,
        dtype="string",
        synonyms=["email", "email address", "e-mail"],
    ))
    registry.register_column_detector(detect_email_header, field="email", priority=60)
    registry.register_column_detector(detect_email_values, field="email", priority=30)
    registry.register_column_transform(normalize_email, field="email", priority=0)
    registry.register_column_validator(validate_email, field="email", priority=0)
    # If you prefer per-cell helpers, uncomment the functions below and register them instead:
    # registry.register_column_transform(normalize_email_cell, field="email", priority=0)
    # registry.register_column_validator(validate_email_cell, field="email", priority=0)


def _norm(text: object | None) -> str:
    return "" if text is None else str(text).strip().lower()


def detect_email_header(ctx: ColumnDetectorContext) -> ScoreMap | None:
    header = _norm(ctx.header)
    if not header:
        return None
    if "email" in header or "e-mail" in header:
        return {"email": 1.0}
    return None


def detect_email_values(ctx: ColumnDetectorContext) -> ScoreMap | None:
    sample = ctx.sample or []
    hits = 0
    total = 0
    for v in sample:
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


def normalize_email(ctx: TransformContext) -> list[ColumnTransformRow]:
    """Return `[{"row_index": int, "value": {"email": ...}}, ...]`."""

    return [
        {
            "row_index": idx,
            "value": {"email": (_norm(v) or None)},
        }
        for idx, v in enumerate(ctx.values)
    ]


def validate_email(ctx: ValidateContext) -> list[ColumnValidatorIssue]:
    """Return `[{"row_index": int, "message": str}, ...]` for invalid cells."""

    issues: list[ColumnValidatorIssue] = []
    for idx, v in enumerate(ctx.values):
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
# def normalize_email_cell(value: object | None) -> ColumnTransformRow:
#     """Return a single normalized email dict for one cell."""
#     return {"row_index": 0, "value": {"email": (_norm(value) or None)}}
#
# def validate_email_cell(value: object | None) -> ColumnValidatorIssue | None:
#     """Validate one email cell; return a single issue or None."""
#     text_value = _norm(value)
#     if text_value and not EMAIL_RE.match(text_value):
#         return {"row_index": 0, "message": f"Invalid email: {value}"}
#     return None
