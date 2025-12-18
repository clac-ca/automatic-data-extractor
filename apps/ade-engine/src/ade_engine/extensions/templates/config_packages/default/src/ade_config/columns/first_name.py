from __future__ import annotations

import re

import polars as pl

from ade_engine.models import FieldDef

FIELD_NAME = "first_name"

_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"first", "name"},
    {"firstname"},
    {"fname"},
    {"given", "name"},
    {"givenname"},
    {"forename"},
]


def register(registry):
    registry.register_field(FieldDef(name=FIELD_NAME, label="First Name", dtype="string"))

    # Enabled by default:
    # Detect "first_name" using common header names.
    registry.register_column_detector(detect_first_name_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # -------------------------------------------------
    # registry.register_column_detector(detect_first_name_values_basic, field=FIELD_NAME, priority=30)
    # registry.register_column_detector(detect_first_name_values_neighbor_pair, field=FIELD_NAME, priority=25)
    # registry.register_column_transform(normalize_first_name, field=FIELD_NAME, priority=0)
    # registry.register_column_validator(validate_first_name, field=FIELD_NAME, priority=0)


def detect_first_name_header_common_names(
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
    """Enabled by default.

    Purpose:
      - Match typical first-name headers ("first name", "fname", "given name", ...).
    """
    raw = (header_text or "").strip().lower()
    if not raw:
        return None

    normalized = _HEADER_NON_ALNUM_RE.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in HEADER_TOKEN_SETS_STRONG):
        return {FIELD_NAME: 1.0}

    return None


def detect_first_name_values_basic(
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
    """Example (disabled by default).

    Purpose:
      - Detect first-name columns from values when headers aren’t useful.
      - Simple heuristic: short, single-token, non-numeric strings.
    """
    if not column_sample:
        return None

    good = 0
    total = 0
    for s in column_sample:
        total += 1
        if any(ch.isdigit() for ch in s):
            continue
        if " " in s:
            continue
        if 2 <= len(s) <= 20:
            good += 1

    return {FIELD_NAME: float(good / total)}


def detect_first_name_values_neighbor_pair(
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
    """Example (disabled by default).

    Purpose:
      - Demonstrate cross-column detection when canonical names are unknown.
      - Uses column_index to look at the *right neighbor* (common layout: First | Last).

    Note:
      - We do not reference "last_name" here because mapping hasn't happened yet.
    """
    if not column_sample:
        return None

    # Base score from this column's sample.
    base_good = 0
    base_total = 0
    for s in column_sample:
        base_total += 1
        if any(ch.isdigit() for ch in s) or " " in s or not (2 <= len(s) <= 20):
            continue
        base_good += 1
    base_score = base_good / base_total

    # Neighbor score from the right column (sampled from the table).
    if column_index + 1 >= len(table.columns):
        return {FIELD_NAME: float(base_score)}

    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    right_col_name = t.columns[column_index + 1]
    right_series = t.get_column(right_col_name)

    right_sample: list[str] = []
    for v in right_series.to_list():
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        right_sample.append(s)
        if len(right_sample) >= text_n:
            break

    if not right_sample:
        return {FIELD_NAME: float(base_score)}

    right_good = 0
    right_total = 0
    for s in right_sample:
        right_total += 1
        if any(ch.isdigit() for ch in s) or " " in s or not (2 <= len(s) <= 20):
            continue
        right_good += 1
    right_score = right_good / right_total

    # Boost only when both columns look strongly "name-ish".
    score = float(base_score)
    if base_score >= 0.7 and right_score >= 0.7:
        score = min(1.0, score + 0.15)

    return {FIELD_NAME: score}


def normalize_first_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Standardize blanks and whitespace.
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_first_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Catch clearly bad data without being overly strict.
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 50))
        .then(pl.lit("First name is unusually long"))
        .otherwise(pl.lit(None))
    )
