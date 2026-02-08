"""Session cookie helpers."""

from __future__ import annotations

from fastapi import Response

from ade_api.settings import Settings


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    secure = settings.public_web_url.lower().startswith("https://")
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(settings.session_access_ttl.total_seconds()),
        path=settings.session_cookie_path or "/",
        domain=settings.session_cookie_domain,
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path=settings.session_cookie_path or "/",
        domain=settings.session_cookie_domain,
    )

