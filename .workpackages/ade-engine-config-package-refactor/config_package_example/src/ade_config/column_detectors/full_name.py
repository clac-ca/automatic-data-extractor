from __future__ import annotations

import re

from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext

# Optional metadata helper; safe to remove if you don't need custom label/required/dtype/synonyms.
@field_meta(name="full_name", label="Full Name", dtype="string", synonyms=["full name", "name", "contact name"])


# --- Detection --------------------------------------------------------------

@column_detector(field="full_name", priority=30)
def detect_full_name_header(ctx: ColumnDetectorContext):
    """Real‑world but simple: exact "full name" boosts, also slightly nudges plain "name"."""

    header = (ctx.header or "").strip().lower()
    if header == "full name":
        return {
            "full_name": 1.0,
            "first_name": -1.0,
            "middle_name": -1.0,
            "last_name": -1.0,
        }
    if header == "name":
        return {"full_name": 0.8}
    return {"full_name": 0.0}


@column_detector(field="full_name", priority=10)
def detect_full_name_values(ctx: ColumnDetectorContext):
    """Look for two-part names ("First Last") or comma names ("Last, First")."""

    sample = ctx.sample or []
    comma_pattern = re.compile(r"^[A-Za-z][\w'\-]*,\s*[A-Za-z][\w'\-]*$")
    space_pattern = re.compile(r"^[A-Za-z][\w'\-]*\s+[A-Za-z][\w'\-]*$")

    matches = 0
    total = 0

    for v in sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        # ignore strings with digits; likely IDs, not names
        if any(ch.isdigit() for ch in s):
            continue
        total += 1
        if comma_pattern.match(s) or space_pattern.match(s):
            matches += 1

    if total == 0:
        return {"full_name": 0.0}

    score = min(1.0, matches / total)
    return {"full_name": score}


# --- Transform -------------------------------------------------------------

@column_transform(field="full_name", priority=0)
def normalize_full_name(ctx: TransformContext):
    """Minimal normalizer that also surfaces split parts.

    Supported shapes:
    - "First Last": split on the space.
    - "Last, First": split on the comma.
    """

    comma_pattern = re.compile(r"^(?P<last>[A-Za-z][\w'\-]*),\s*(?P<first>[A-Za-z][\w'\-]*)$")

    normalized_rows = []

    for raw_value in ctx.values:
        text_value = None if raw_value is None else str(raw_value).strip()
        if not text_value:
            normalized_rows.append({
                "full_name": None,
                "first_name": None,
                "last_name": None,
            })
            continue

        first_name: str | None = None
        last_name: str | None = None

        comma_match = comma_pattern.match(text_value)
        if comma_match:
            last_name = comma_match.group("last")
            first_name = comma_match.group("first")
        else:
            parts = text_value.split()
            if len(parts) == 2:
                first_name, last_name = parts
            else:
                normalized_rows.append({
                    "full_name": text_value,
                    "first_name": None,
                    "last_name": None,
                })
                continue

        full_name = f"{first_name} {last_name}".strip()

        normalized_rows.append({
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
        })

    return normalized_rows


# --- Validation ------------------------------------------------------------

@column_validator(field="full_name", priority=0)
def validate_full_name(ctx: ValidateContext):
    """Allow letters, spaces, apostrophes, and hyphens; reject digits/symbols."""

    issues = []
    pattern = re.compile(r"^[A-Za-z][A-Za-z '\-]*$")

    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if not s:
            continue
        if not pattern.fullmatch(s):
            issues.append({
                "passed": False,
                "message": "Full name must be letters with spaces/hyphens/apostrophes",
                "row_index": idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })

    return issues or {"passed": True}
