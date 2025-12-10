from __future__ import annotations

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="last_name", label="Last Name", dtype="string", synonyms=["last name", "surname", "family name", "lname"])

@column_detector(field="last_name", priority=50)
def detect_last_name_header(ctx: ColumnDetectorContext):
    t = set((ctx.header or "").lower().replace("-", " ").split())
    if not t:
        return {"last_name": 0.0}
    if ("last" in t and "name" in t) or "surname" in t or "family" in t:
        return {"last_name": 1.0}
    if "lname" in t:
        return {"last_name": 0.9}
    return {"last_name": 0.0}


@column_detector(field="last_name", priority=20)
def detect_last_name_values(ctx: ColumnDetectorContext):
    sample = ctx.sample or []
    total = 0
    longish = 0
    for v in sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if len(s) >= 2 and " " not in s:
            longish += 1
    if total == 0:
        return {"last_name": 0.0}
    score = min(1.0, longish / total)
    return {"last_name": score}


@column_transform(field="last_name", priority=0)
def normalize_last_name(ctx: TransformContext):
    return [
        {"last_name": (None if v is None else str(v).strip() or None)}
        for v in ctx.values
    ]


@column_validator(field="last_name", priority=0)
def validate_last_name(ctx: ValidateContext):
    issues = []
    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if s and len(s) > 80:
            issues.append({
                "passed": False,
                "message": "Last name too long",
                "row_index": idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
