"""CSRF helper utilities for double-submit cookie flows."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Response

from ade_api.settings import Settings


@dataclass(frozen=True, slots=True)
class CookieSettings:
    secure: bool
    samesite: str


def _resolve_cookie_settings(settings: Settings) -> CookieSettings:
    frontend_url = settings.frontend_url or settings.server_public_url
    try:
        frontend = urlparse(frontend_url)
        server = urlparse(settings.server_public_url)
        cross_origin = (frontend.scheme, frontend.netloc) != (server.scheme, server.netloc)
    except Exception:
        cross_origin = False

    if cross_origin:
        return CookieSettings(secure=True, samesite="none")

    secure = settings.server_public_url.lower().startswith("https://")
    return CookieSettings(secure=secure, samesite="lax")


def mint_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response,
    settings: Settings,
    *,
    token: str | None = None,
) -> str:
    value = token or mint_csrf_token()
    cookie = _resolve_cookie_settings(settings)
    response.set_cookie(
        key=settings.session_csrf_cookie_name,
        value=value,
        max_age=int(settings.session_access_ttl.total_seconds()),
        path=settings.session_cookie_path or "/",
        domain=settings.session_cookie_domain,
        secure=cookie.secure,
        httponly=False,
        samesite=cookie.samesite,
    )
    return value


def clear_csrf_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_csrf_cookie_name,
        path=settings.session_cookie_path or "/",
        domain=settings.session_cookie_domain,
    )


__all__ = ["clear_csrf_cookie", "mint_csrf_token", "set_csrf_cookie"]
