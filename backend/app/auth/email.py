"""Email address validation and canonicalisation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


class EmailValidationError(ValueError):
    """Raised when an email address fails validation."""


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    """Canonical representation of an email address."""

    original: str
    canonical: str


def normalize_email(value: str) -> NormalizedEmail:
    """Validate an email and return display + canonical forms.

    The canonical value is suitable for comparisons, uniqueness constraints,
    and lookups. The original value preserves the caller's casing so UIs can
    continue showing email addresses exactly as they were provided.
    """

    trimmed = value.strip()
    if not trimmed:
        raise EmailValidationError("Email address must not be empty")

    try:
        result = validate_email(
            trimmed,
            allow_smtputf8=True,
            check_deliverability=False,
            globally_deliverable=False,
        )
    except EmailNotValidError as exc:
        raise EmailValidationError("Invalid email address") from exc

    local_part = result.local_part.casefold()
    domain = (result.ascii_domain or result.domain or "").casefold()
    canonical = f"{local_part}@{domain}" if domain else local_part
    if not canonical:
        raise EmailValidationError("Canonical email could not be determined")

    original = result.original or trimmed
    return NormalizedEmail(original=original, canonical=canonical)


def canonicalize_email(value: str) -> str:
    """Return the canonical representation of an email address."""

    return normalize_email(value).canonical


__all__ = [
    "EmailValidationError",
    "NormalizedEmail",
    "canonicalize_email",
    "normalize_email",
]
