from __future__ import annotations

import re

import polars as pl

from ade_engine.models import FieldDef

# Teaching note:
# Keep patterns simple. This is intentionally "good enough" for a template.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
EMAIL_RE = re.compile(EMAIL_PATTERN)


def register(registry):
    registry.register_field(FieldDef(name="email", dtype="string"))
    registry.register_column_detector(detect_email_header, field="email", priority=60)
    registry.register_column_detector(detect_email_values, field="email", priority=30)
    registry.register_column_transform(normalize_email, field="email", priority=0)
    registry.register_column_validator(validate_email, field="email", priority=0)


def detect_email_header(
    *,
    table: pl.DataFrame,  # Table DF (pre-mapping; extracted headers, data rows only)
    column: pl.Series,  # Current column Series (same as table.get_column(column_name))
    column_sample: list[str],  # Trimmed, non-empty string sample from this column
    column_name: str,  # Current DF column name (extracted header; not canonical)
    column_index: int,  # 0-based index of this column in table.columns
    header_text: str,  # Trimmed header cell text for this column ("" if missing)
    settings,  # Engine Settings (sampling is controlled by engine settings)
    sheet_name: str,  # Worksheet title
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Header-based detection: fast and high confidence."""
    header = (header_text or "").strip().lower()
    if not header:
        return None

    if "email" in header or "e-mail" in header:
        return {"email": 1.0}

    return None


def detect_email_values(
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
    """Value-based detection using the engine-provided sample.

    Teaching notes:
    - `column_sample` is already trimmed + non-empty + capped by settings.
    - Keep value detectors simple; do not rescan the full table unless needed.
    """
    if not column_sample:
        return None

    matches = 0
    total = 0

    for s in column_sample:
        total += 1
        if EMAIL_RE.fullmatch(s.lower()):
            matches += 1

    score = matches / total
    return {"email": float(score)}


def normalize_email(
    *,
    field_name: str,  # Canonical field name being transformed (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Trim, lowercase, and convert empty -> null."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars().str.to_lowercase()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_email(
    *,
    field_name: str,  # Canonical field name being validated (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Format validation.

    Returns a string message when invalid, otherwise null.
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars().str.to_lowercase()

    return (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(EMAIL_PATTERN))
        .then(pl.concat_str([pl.lit("Invalid email: "), v]))
        .otherwise(pl.lit(None))
    )
