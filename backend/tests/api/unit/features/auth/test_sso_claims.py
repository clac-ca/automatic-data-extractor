from __future__ import annotations

import pytest

from ade_api.features.auth.sso_claims import (
    resolve_email,
    resolve_email_verified_signal,
    resolve_subject_key,
)


def test_resolve_subject_key_uses_tid_oid_for_entra_tokens() -> None:
    claims = {
        "sub": "legacy-subject",
        "tid": "tenant-id",
        "oid": "object-id",
    }

    subject = resolve_subject_key("https://login.microsoftonline.com/tenant-id/v2.0", claims)

    assert subject == "tenant-id:object-id"


def test_resolve_subject_key_uses_sub_for_non_entra_tokens() -> None:
    claims = {"sub": "subject-123"}

    subject = resolve_subject_key("https://issuer.example.com", claims)

    assert subject == "subject-123"


def test_resolve_subject_key_requires_tid_oid_for_entra_issuer() -> None:
    with pytest.raises(ValueError):
        resolve_subject_key(
            "https://login.microsoftonline.com/tenant-id/v2.0",
            {"sub": "legacy-subject"},
        )


def test_resolve_email_uses_expected_claim_fallback_order() -> None:
    assert resolve_email({"email": "user@example.com", "preferred_username": "ignored@example.com"}) == (
        "user@example.com"
    )
    assert resolve_email({"preferred_username": "preferred@example.com"}) == "preferred@example.com"
    assert resolve_email({"upn": "upn@example.com"}) == "upn@example.com"


def test_resolve_email_returns_none_when_no_usable_email_claim_exists() -> None:
    assert resolve_email({"preferred_username": "not-an-email"}) is None
    assert resolve_email({}) is None


def test_resolve_email_verified_signal_supports_entra_claims() -> None:
    assert resolve_email_verified_signal({"email_verified": True}) is True
    assert resolve_email_verified_signal({"xms_edov": "true"}) is True
    assert resolve_email_verified_signal({"verified_primary_email": "user@example.com"}) is True
    assert resolve_email_verified_signal({}) is False
