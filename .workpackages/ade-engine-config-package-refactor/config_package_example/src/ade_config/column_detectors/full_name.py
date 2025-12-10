from __future__ import annotations

import re

from ade_engine.registry.models import ColumnDetectorContext, FieldDef, TransformContext, ValidateContext


def register(registry):
    registry.register_field(FieldDef(
        name="full_name",
        label="Full Name",
        dtype="string",
        synonyms=["full name", "name", "contact name"],
    ))
    registry.register_column_detector(detect_full_name_header, field="full_name", priority=30)
    registry.register_column_detector(detect_full_name_values, field="full_name", priority=10)
    registry.register_column_transform(normalize_full_name, field="full_name", priority=0)
    registry.register_column_validator(validate_full_name, field="full_name", priority=0)


def detect_full_name_header(ctx: ColumnDetectorContext):
    """Real-world but simple: exact "full name" boosts, also slightly nudges plain "name"."""

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

# Example cell-level helpers (commented out):
# These show the per-cell shape; they are just wrappers that process one cell at a time.
# Prefer the column-level transforms/validators above when you want to touch multiple
# fields at once or keep things more performant.
#
# def normalize_full_name_cell(value: object | None):
#     text_value = None if value is None else str(value).strip()
#     return {"full_name": (text_value or None)}
#
# def validate_full_name_cell(value: object | None):
#     text_value = "" if value is None else str(value).strip()
#     if text_value and not pattern.fullmatch(text_value):
#         return {"passed": False, "message": "Full name must be letters with spaces/hyphens/apostrophes", "value": value}
#     return {"passed": True}
