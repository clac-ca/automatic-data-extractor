"""Runtime password complexity validation helpers."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass

from fastapi import status

from ade_api.common.problem_details import ApiError, ProblemDetailsErrorItem

_UPPERCASE = string.ascii_uppercase
_LOWERCASE = string.ascii_lowercase
_DIGITS = string.digits
_SYMBOLS = "!@#$%^&*()-_=+[]{}:;,.?"


@dataclass(frozen=True, slots=True)
class PasswordComplexityPolicy:
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_number: bool
    require_symbol: bool


def enforce_password_complexity(
    password: str,
    *,
    policy: PasswordComplexityPolicy,
    field_path: str,
) -> None:
    """Raise a validation error when ``password`` violates runtime complexity policy."""

    errors: list[ProblemDetailsErrorItem] = []
    if len(password) < policy.min_length:
        errors.append(
            ProblemDetailsErrorItem(
                path=field_path,
                code="password_too_short",
                message=f"Password must be at least {policy.min_length} characters.",
            )
        )
    if policy.require_uppercase and not any(character.isupper() for character in password):
        errors.append(
            ProblemDetailsErrorItem(
                path=field_path,
                code="password_missing_uppercase",
                message="Password must include at least one uppercase letter.",
            )
        )
    if policy.require_lowercase and not any(character.islower() for character in password):
        errors.append(
            ProblemDetailsErrorItem(
                path=field_path,
                code="password_missing_lowercase",
                message="Password must include at least one lowercase letter.",
            )
        )
    if policy.require_number and not any(character.isdigit() for character in password):
        errors.append(
            ProblemDetailsErrorItem(
                path=field_path,
                code="password_missing_number",
                message="Password must include at least one number.",
            )
        )
    if policy.require_symbol and password.isalnum():
        errors.append(
            ProblemDetailsErrorItem(
                path=field_path,
                code="password_missing_symbol",
                message="Password must include at least one symbol.",
            )
        )

    if errors:
        raise ApiError(
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password does not meet complexity requirements.",
            errors=errors,
        )


def generate_password_for_policy(
    *,
    policy: PasswordComplexityPolicy,
    length: int | None = None,
) -> str:
    """Generate a random password that satisfies ``policy``."""

    target_length = max(length or 20, policy.min_length)
    required_sets: list[str] = []
    if policy.require_uppercase:
        required_sets.append(_UPPERCASE)
    if policy.require_lowercase:
        required_sets.append(_LOWERCASE)
    if policy.require_number:
        required_sets.append(_DIGITS)
    if policy.require_symbol:
        required_sets.append(_SYMBOLS)

    if len(required_sets) > target_length:
        target_length = len(required_sets)

    base_pool = _LOWERCASE + _UPPERCASE + _DIGITS + _SYMBOLS
    for _ in range(32):
        chars = [secrets.choice(pool) for pool in required_sets]
        chars.extend(secrets.choice(base_pool) for _ in range(target_length - len(chars)))
        secrets.SystemRandom().shuffle(chars)
        candidate = "".join(chars)
        try:
            enforce_password_complexity(
                candidate,
                policy=policy,
                field_path="password",
            )
        except ApiError:
            continue
        return candidate

    raise RuntimeError("Unable to generate password meeting runtime complexity policy.")
