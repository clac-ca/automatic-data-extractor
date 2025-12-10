from __future__ import annotations

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="middle_name", label="Middle Name", dtype="string", synonyms=["middle name", "mname", "middle initial"])

@column_detector(field="middle_name", priority=40)
def detect_middle_name_header(
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
    t = set((header or "").lower().replace("-", " ").split())
    if not t:
        return {"middle_name": 0.0}
    if ("middle" in t and "name" in t) or "m.i" in (header or "").lower():
        return {"middle_name": 1.0}
    if "mi" in t or "middle" in t:
        return {"middle_name": 0.8}
    return {"middle_name": 0.0}


@column_detector(field="middle_name", priority=15)
def detect_middle_name_values(
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
    initials = 0
    total = 0
    for v in values_sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if len(s) == 1 or (len(s) == 2 and "." in s):
            initials += 1
    if total == 0:
        return {"middle_name": 0.0}
    score = min(1.0, initials / total)
    return {"middle_name": score}


@column_transform(field="middle_name", priority=0)
def normalize_middle_name(
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
            "value": {"middle_name": (None if v is None else str(v).strip() or None)},
        }
        for idx, v in enumerate(values)
    ]


@column_validator(field="middle_name", priority=0)
def validate_middle_name(
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
        if len(s) > 40:
            issues.append({
                "row_index": idx,
                "message": "Middle name too long",
            })
    return issues
