"""Normalization helpers for document tags."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

MAX_TAG_LENGTH = 100
MAX_TAGS_PER_DOCUMENT = 50
MIN_TAG_SEARCH_LEN = 2


class TagValidationError(ValueError):
    """Raised when a tag payload violates normalization rules."""


def _strip_control_chars(value: str) -> str:
    return "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")


def normalize_tag_value(value: str) -> str:
    """Return a normalized tag string or raise ``TagValidationError``."""

    if not isinstance(value, str):
        raise TagValidationError("Tag values must be strings.")

    filtered = _strip_control_chars(value)
    collapsed = " ".join(filtered.split())
    normalized = collapsed.casefold()

    if not normalized:
        raise TagValidationError("Tag values must not be empty.")
    if len(normalized) > MAX_TAG_LENGTH:
        raise TagValidationError(f"Tag values must be at most {MAX_TAG_LENGTH} characters.")

    return normalized


def normalize_tag_list(
    values: Iterable[str],
    *,
    max_tags: int | None = None,
) -> list[str]:
    """Normalize and deduplicate tag values while preserving first-seen order."""

    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        tag = normalize_tag_value(value)
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)

    if max_tags is not None and len(normalized) > max_tags:
        raise TagValidationError(f"Too many tags; max {max_tags}.")

    return normalized


def normalize_tag_set(
    values: Iterable[str],
    *,
    max_tags: int | None = None,
) -> set[str]:
    """Normalize tag values into a set."""

    return set(normalize_tag_list(values, max_tags=max_tags))


def normalize_tag_query(value: str | None) -> str | None:
    """Normalize tag search input while allowing empty values."""

    if value is None:
        return None

    filtered = _strip_control_chars(value)
    collapsed = " ".join(filtered.split())
    if not collapsed:
        return None

    normalized = collapsed.casefold()
    if len(normalized) < MIN_TAG_SEARCH_LEN:
        raise TagValidationError(f"Tag search must be at least {MIN_TAG_SEARCH_LEN} characters.")
    if len(normalized) > MAX_TAG_LENGTH:
        raise TagValidationError(f"Tag search must be at most {MAX_TAG_LENGTH} characters.")

    return normalized


__all__ = [
    "MAX_TAG_LENGTH",
    "MAX_TAGS_PER_DOCUMENT",
    "MIN_TAG_SEARCH_LEN",
    "TagValidationError",
    "normalize_tag_list",
    "normalize_tag_query",
    "normalize_tag_set",
    "normalize_tag_value",
]
