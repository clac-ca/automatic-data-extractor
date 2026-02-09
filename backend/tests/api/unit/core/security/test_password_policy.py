from __future__ import annotations

import pytest

from ade_api.common.problem_details import ApiError
from ade_api.core.security.password_policy import (
    PasswordComplexityPolicy,
    enforce_password_complexity,
    generate_password_for_policy,
)


def test_generate_password_for_policy_satisfies_all_enabled_rules() -> None:
    policy = PasswordComplexityPolicy(
        min_length=18,
        require_uppercase=True,
        require_lowercase=True,
        require_number=True,
        require_symbol=True,
    )

    generated = generate_password_for_policy(policy=policy)

    assert len(generated) >= 18
    assert any(character.isupper() for character in generated)
    assert any(character.islower() for character in generated)
    assert any(character.isdigit() for character in generated)
    assert any(not character.isalnum() for character in generated)

    enforce_password_complexity(generated, policy=policy, field_path="password")


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("short1A!", "password_too_short"),
        ("lowercase123!", "password_missing_uppercase"),
        ("UPPERCASE123!", "password_missing_lowercase"),
        ("NoNumbers!", "password_missing_number"),
        ("NoSymbols123", "password_missing_symbol"),
    ],
)
def test_enforce_password_complexity_reports_expected_code(password: str, code: str) -> None:
    policy = PasswordComplexityPolicy(
        min_length=12,
        require_uppercase=True,
        require_lowercase=True,
        require_number=True,
        require_symbol=True,
    )

    with pytest.raises(ApiError) as exc_info:
        enforce_password_complexity(
            password,
            policy=policy,
            field_path="password",
        )

    codes = {item.code for item in (exc_info.value.errors or [])}
    assert code in codes
