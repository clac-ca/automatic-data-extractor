from __future__ import annotations

import polars as pl

from ade_engine.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="middle_name", label="Middle Name", dtype="string"))
    registry.register_column_detector(detect_middle_name_header, field="middle_name", priority=40)
    registry.register_column_detector(detect_middle_name_values, field="middle_name", priority=15)
    registry.register_column_transform(normalize_middle_name, field="middle_name", priority=0)
    registry.register_column_validator(validate_middle_name, field="middle_name", priority=0)


def detect_middle_name_header(
    *,
    table: pl.DataFrame,
    column: pl.Series,
    column_sample: list[str],
    column_name: str,
    column_index: int,
    header_text: str,
    settings,
    sheet_name: str,
    metadata: dict,
    state: dict,
    input_file_name: str | None,
    logger,
) -> dict[str, float] | None:
    """Header-based detection for middle_name / middle initial."""
    tokens = set((header_text or "").lower().replace("-", " ").split())
    header_lower = (header_text or "").lower()

    if not tokens and not header_lower:
        return None

    if ("middle" in tokens and "name" in tokens) or "m.i" in header_lower:
        return {"middle_name": 1.0}
    if "mi" in tokens or "middle" in tokens:
        return {"middle_name": 0.8}

    return None


def detect_middle_name_values(
    *,
    table: pl.DataFrame,
    column: pl.Series,
    column_sample: list[str],
    column_name: str,
    column_index: int,
    header_text: str,
    settings,
    sheet_name: str,
    metadata: dict,
    state: dict,
    input_file_name: str | None,
    logger,
) -> dict[str, float] | None:
    """Value-based detection for middle initials.

    Heuristic (simple):
    - values often look like "A" or "A."
    """
    if not column_sample:
        return None

    matches = 0
    total = 0

    for s in column_sample:
        total += 1
        if len(s) == 1 and s.isalpha():
            matches += 1
        elif len(s) == 2 and s[0].isalpha() and s[1] == ".":
            matches += 1

    score = matches / total
    return {"middle_name": float(score)}


def normalize_middle_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Trim and convert empty -> null."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_middle_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 40))
        .then(pl.lit("Middle name too long"))
        .otherwise(pl.lit(None))
    )
