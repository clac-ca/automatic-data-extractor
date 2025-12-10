from __future__ import annotations

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="first_name", label="First Name", dtype="string", synonyms=["first name", "given name", "fname"])


@column_detector(field="first_name", priority=50)
def detect_first_name_header(
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
    header_tokens = set((header or "").lower().replace("-", " ").split())
    if not header_tokens:
        return {"first_name": 0.0}
    if "first" in header_tokens and "name" in header_tokens:
        return {"first_name": 1.0}
    if "fname" in header_tokens or "given" in header_tokens:
        return {"first_name": 0.9}
    return {"first_name": 0.0}


@column_detector(field="first_name", priority=20)
def detect_first_name_values(
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
    if not values_sample:
        return {"first_name": 0.0}
    shortish = 0
    total = 0
    for v in values_sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if 2 <= len(s) <= 20 and " " not in s:
            shortish += 1
    if total == 0:
        return {"first_name": 0.0}
    score = min(1.0, shortish / total)
    return {"first_name": score}


@column_transform(field="first_name", priority=0)
def normalize_first_name(
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
            "value": {"first_name": (None if v is None else str(v).strip() or None)},
        }
        for idx, v in enumerate(values)
    ]


@column_validator(field="first_name", priority=0)
def validate_first_name(
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
        s = "" if v is None else str(v).strip()
        if s and len(s) > 50:
            issues.append({
                "row_index": idx,
                "message": "First name too long",
            })
    return issues
