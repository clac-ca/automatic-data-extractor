from __future__ import annotations

import re


def header_tokens(text: object | None) -> set[str]:
    """Tokenize a header cell into lowercase words for detectors."""

    if text is None:
        return set()

    normalized = re.sub(r"[^a-z0-9]+", " ", str(text).lower())
    return {tok for tok in normalized.split() if tok}


__all__ = ["header_tokens"]
