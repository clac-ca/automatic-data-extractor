from __future__ import annotations

import re

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="email", label="Email", required=True, dtype="string", synonyms=["email", "email address", "e-mail"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm(text: object | None) -> str:
    return "" if text is None else str(text).strip().lower()


@column_detector(field="email", priority=60)
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
):
    header = _norm(header)
    if not header:
        return {"email": 0.0}
    if "email" in header or "e-mail" in header:
        return {"email": 1.0}
    return {"email": 0.0}


@column_detector(field="email", priority=30)
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
):
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
        return {"email": 0.0}
    score = min(1.0, hits / total)
    return {"email": score}


@column_transform(field="email", priority=0)
def normalize_email(
    *,
    field_name,
    values,
    mapping,
    state,
    metadata,
    input_file_name,
    logger,
):
    return [
        {
            "row_index": idx,
            "value": {"email": (_norm(v) or None)},
        }
        for idx, v in enumerate(values)
    ]


@column_validator(field="email", priority=0)
def validate_email(
    *,
    field_name,
    values,
    mapping,
    state,
    metadata,
    column_index,
    input_file_name,
    logger,
):
    issues = []
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
