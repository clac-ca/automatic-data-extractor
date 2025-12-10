from __future__ import annotations

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="middle_name", label="Middle Name", dtype="string", synonyms=["middle name", "mname", "middle initial"])

@column_detector(field="middle_name", priority=40)
def detect_middle_name_header(ctx: ColumnDetectorContext):
    t = set((ctx.header or "").lower().replace("-", " ").split())
    if not t:
        return {"middle_name": 0.0}
    if ("middle" in t and "name" in t) or "m.i" in ctx.header.lower():
        return {"middle_name": 1.0}
    if "mi" in t or "middle" in t:
        return {"middle_name": 0.8}
    return {"middle_name": 0.0}


@column_detector(field="middle_name", priority=15)
def detect_middle_name_values(ctx: ColumnDetectorContext):
    sample = ctx.column_values_sample or []
    initials = 0
    total = 0
    for v in sample:
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
def normalize_middle_name(ctx: TransformContext):
    return [
        {"middle_name": (None if v is None else str(v).strip() or None)}
        for v in ctx.values
    ]


@column_validator(field="middle_name", priority=0)
def validate_middle_name(ctx: ValidateContext):
    issues = []
    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if len(s) > 40:
            issues.append({
                "passed": False,
                "message": "Middle name too long",
                "row_index": idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
