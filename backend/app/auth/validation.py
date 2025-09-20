"""Configuration validation for ADE authentication."""

from __future__ import annotations

from .. import config


def validate_settings(settings: config.Settings) -> None:
    """Raise ``RuntimeError`` when authentication settings are invalid."""

    try:
        modes = settings.auth_mode_sequence
    except ValueError as exc:  # pragma: no cover - defensive
        raise RuntimeError(str(exc)) from exc

    if not modes:
        raise RuntimeError("ADE_AUTH_MODES must enable at least one authentication mode")

    if "session" in modes:
        if settings.session_cookie_same_site == "none" and not settings.session_cookie_secure:
            raise RuntimeError(
                "ADE_SESSION_COOKIE_SECURE must be enabled when SameSite is set to 'none'"
            )

    if "sso" in modes:
        required = {
            "ADE_SSO_CLIENT_ID": settings.sso_client_id,
            "ADE_SSO_CLIENT_SECRET": settings.sso_client_secret,
            "ADE_SSO_ISSUER": settings.sso_issuer,
            "ADE_SSO_REDIRECT_URL": settings.sso_redirect_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(sorted(missing))
            raise RuntimeError(f"Missing SSO configuration values: {joined}")

    if settings.admin_email_allowlist_enabled and not settings.admin_allowlist:
        raise RuntimeError(
            "ADE_ADMIN_EMAIL_ALLOWLIST must list at least one address when the allowlist is enabled"
        )


__all__ = ["validate_settings"]
