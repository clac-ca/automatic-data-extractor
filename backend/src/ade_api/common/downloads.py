"""Download-related helpers (safe filenames, headers)."""

from __future__ import annotations

import mimetypes
import unicodedata
from pathlib import Path
from urllib.parse import quote

_DEFAULT_DOWNLOAD_FILENAME = "download"
_MAX_FILENAME_LENGTH = 255

__all__ = [
    "build_canonical_download_filename",
    "build_content_disposition",
    "derive_artifact_extension",
]


def _strip_control_chars(value: str) -> str:
    return "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")


def _extract_suffix(filename: str | None) -> str:
    if not filename:
        return ""
    cleaned = _strip_control_chars(filename).strip()
    if not cleaned:
        return ""
    suffix = Path(cleaned).suffix.strip()
    if not suffix or suffix == ".":
        return ""
    return suffix.lower()


def _suffix_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    normalized = content_type.split(";", 1)[0].strip().lower()
    if not normalized:
        return ""
    guessed = mimetypes.guess_extension(normalized, strict=False)
    if guessed is None:
        guessed = mimetypes.guess_extension(normalized)
    return guessed.lower() if guessed else ""


def derive_artifact_extension(
    *,
    version_filename: str | None = None,
    artifact_filename: str | None = None,
    content_type: str | None = None,
    fallback_filename: str | None = None,
) -> str:
    """Resolve artifact extension using the download naming precedence."""

    suffix = _extract_suffix(version_filename)
    if suffix:
        return suffix

    suffix = _extract_suffix(artifact_filename)
    if suffix:
        return suffix

    suffix = _suffix_from_content_type(content_type)
    if suffix:
        return suffix

    return _extract_suffix(fallback_filename)


def build_canonical_download_filename(
    *,
    document_name: str | None,
    version_filename: str | None = None,
    artifact_filename: str | None = None,
    content_type: str | None = None,
    default: str = _DEFAULT_DOWNLOAD_FILENAME,
    max_length: int = _MAX_FILENAME_LENGTH,
) -> str:
    """Build a canonical download name from display-name stem and artifact extension."""

    length = max(1, max_length)
    safe_default = (_strip_control_chars(default).strip() or _DEFAULT_DOWNLOAD_FILENAME)[:length]

    cleaned_document_name = _strip_control_chars((document_name or "").strip())
    stem = Path(cleaned_document_name).stem.strip() or safe_default

    suffix = derive_artifact_extension(
        version_filename=version_filename,
        artifact_filename=artifact_filename,
        content_type=content_type,
        fallback_filename=document_name,
    )

    max_stem_length = max(1, length - len(suffix))
    trimmed_stem = stem[:max_stem_length].rstrip() or safe_default
    filename = f"{trimmed_stem}{suffix}"
    return filename[:length] or safe_default


def build_content_disposition(filename: str, *, default: str = "download") -> str:
    """Return a safe ``Content-Disposition`` header value for ``filename``.

    We generate both an ASCII fallback ``filename`` and a UTF-8 encoded
    ``filename*`` so browsers can correctly display non-ASCII filenames.
    """
    stripped = filename.strip()
    cleaned = _strip_control_chars(stripped).strip()
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
