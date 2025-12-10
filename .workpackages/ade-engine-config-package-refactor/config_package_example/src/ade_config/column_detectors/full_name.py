from __future__ import annotations

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="full_name", label="Full Name", dtype="string", synonyms=["full name", "name", "contact name"])

@column_detector(field="full_name", priority=30)
def detect_full_name_header(ctx: ColumnDetectorContext):
    t = set((ctx.header or "").lower().replace("-", " ").split())
    if not t:
        return {"full_name": 0.0}
    if "full" in t and "name" in t:
        return {"full_name": 1.0}
    if "name" in t:
        return {"full_name": 0.6}
    return {"full_name": 0.0}


@column_detector(field="full_name", priority=10)
def detect_full_name_values(ctx: ColumnDetectorContext):
    sample = ctx.column_values_sample or []
    spaced = 0
    total = 0
    for v in sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if " " in s:
            spaced += 1
    if total == 0:
        return {"full_name": 0.0}
    score = min(1.0, spaced / total)
    return {"full_name": score}


@column_transform(field="full_name", priority=0)
def pass_through_full_name(ctx: TransformContext):
    return [
        {"full_name": (None if v is None else str(v).strip() or None)}
        for v in ctx.values
    ]


@column_validator(field="full_name", priority=0)
def validate_full_name(ctx: ValidateContext):
    issues = []
    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if len(s) > 120:
            issues.append({
                "passed": False,
                "message": "Full name too long",
                "row_index": idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
