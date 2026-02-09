"""Download-related helpers (safe filenames, headers)."""

from __future__ import annotations

import unicodedata
from urllib.parse import quote

__all__ = ["build_content_disposition"]


def build_content_disposition(filename: str, *, default: str = "download") -> str:
    """Return a safe ``Content-Disposition`` header value for ``filename``.

    We generate both an ASCII fallback ``filename`` and a UTF-8 encoded
    ``filename*`` so browsers can correctly display non-ASCII filenames.
    """
    stripped = filename.strip()
    cleaned = "".join(ch for ch in stripped if unicodedata.category(ch)[0] != "C").strip()
    candidate = cleaned or default

    fallback_chars: list[str] = []
    for char in candidate:
        code_point = ord(char)
        if 32 <= code_point < 127 and char not in {'"', "\\", ";", ":"}:
            fallback_chars.append(char)
        else:
            fallback_chars.append("_")

    fallback = "".join(fallback_chars).strip("_ ") or default
    fallback = fallback[:255]

    encoded = quote(candidate, safe="")
    if fallback == candidate:
        return f'attachment; filename="{fallback}"'

    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
