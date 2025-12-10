from __future__ import annotations

import re

from ade_engine.registry.models import ColumnDetectorContext, FieldDef, TransformContext, ValidateContext

from ade_config.column_detectors.types import ColumnTransformRow, ColumnValidatorIssue, ScoreMap

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


def detect_full_name_header(ctx: ColumnDetectorContext) -> ScoreMap | None:
    """Real-world but simple: exact "full name" boosts, also slightly nudges plain "name"."""

    header = ("" if ctx.header in (None, "") else str(ctx.header)).strip().lower()
    if header == "full name":
        return {"full_name": 1.0}
    if header == "name":
        return {"full_name": 0.8}
    return None


def detect_full_name_values(ctx: ColumnDetectorContext) -> ScoreMap | None:
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
        return None

    score = min(1.0, matches / total)
    return {"full_name": score}


def normalize_full_name(ctx: TransformContext) -> list[ColumnTransformRow]:
    """Return `[{"row_index": int, "value": {...}}, ...]`, splitting full names where possible.

    Supported shapes:
    - "First Last": split on the space.
    - "Last, First": split on the comma.
    """

    comma_pattern = re.compile(r"^(?P<last>[A-Za-z][\w'\-]*),\s*(?P<first>[A-Za-z][\w'\-]*)$")

    normalized_rows: list[ColumnTransformRow] = []

    for idx, raw_value in enumerate(ctx.values):
        text_value = None if raw_value is None else str(raw_value).strip()
        if not text_value:
            normalized_rows.append({
                "row_index": idx,
                "value": {
                    "full_name": None,
                    "first_name": None,
                    "last_name": None,
                },
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
                    "row_index": idx,
                    "value": {
                        "full_name": text_value,
                        "first_name": None,
                        "last_name": None,
                    },
                })
                continue

        full_name = f"{first_name} {last_name}".strip()

        normalized_rows.append({
            "row_index": idx,
            "value": {
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
            },
        })

    return normalized_rows


def validate_full_name(ctx: ValidateContext) -> list[ColumnValidatorIssue]:
    """Return `[{"row_index": int, "message": str}, ...]` when names include invalid symbols."""

    issues: list[ColumnValidatorIssue] = []
    pattern = re.compile(r"^[A-Za-z][A-Za-z '\-]*$")

    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if not s:
            continue
        if not pattern.fullmatch(s):
            issues.append({
                "row_index": idx,
                "message": "Full name must be letters with spaces/hyphens/apostrophes",
            })

    return issues

# Example cell-level helpers (commented out):
# These show the per-cell shape; they are just wrappers that process one cell at a time.
# Prefer the column-level transforms/validators above when you want to touch multiple
# fields at once or keep things more performant.
#
# def normalize_full_name_cell(value: object | None) -> ColumnTransformRow:
#     text_value = None if value is None else str(value).strip()
#     return {"row_index": 0, "value": {"full_name": (text_value or None)}}
#
# def validate_full_name_cell(value: object | None) -> ColumnValidatorIssue | None:
#     text_value = "" if value is None else str(value).strip()
#     if text_value and not pattern.fullmatch(text_value):
#         return {"row_index": 0, "message": "Full name must be letters with spaces/hyphens/apostrophes"}
#     return None
