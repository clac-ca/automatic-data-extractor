from __future__ import annotations

import re

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="email", label="Email", required=True, dtype="string", synonyms=["email", "email address", "e-mail"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm(text: object | None) -> str:
    return "" if text is None else str(text).strip().lower()


@column_detector(field="email", priority=60)
def detect_email_header(ctx: ColumnDetectorContext):
    header = _norm(ctx.header)
    if not header:
        return {"email": 0.0}
    if "email" in header or "e-mail" in header:
        return {"email": 1.0}
    return {"email": 0.0}


@column_detector(field="email", priority=30)
def detect_email_values(ctx: ColumnDetectorContext):
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
        return {"email": 0.0}
    score = min(1.0, hits / total)
    return {"email": score}


@column_transform(field="email", priority=0)
def normalize_email(ctx: TransformContext):
    return [
        {"email": (_norm(v) or None)}
        for v in ctx.values
    ]


@column_validator(field="email", priority=0)
def validate_email(ctx: ValidateContext):
    issues = []
    for idx, v in enumerate(ctx.values):
        s = _norm(v)
        if not s:
            continue
        if not EMAIL_RE.match(s):
            issues.append({
                "passed": False,
                "message": f"Invalid email: {v}",
                "row_index": idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
