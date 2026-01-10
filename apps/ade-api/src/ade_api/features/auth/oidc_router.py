"""OIDC SSO endpoints backed by Authlib."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote, urlparse

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from ade_api.common.time import utc_now
from ade_api.core.auth.users import SyncAccessTokenDatabase, get_cookie_transport, get_password_helper
from ade_api.core.http.csrf import set_csrf_cookie
from ade_api.db import get_sessionmaker
from ade_api.models import AccessToken, OAuthAccount, User
from ade_api.settings import Settings, get_settings

router = APIRouter(tags=["auth"])


def _resolve_cookie_params(settings: Settings) -> dict[str, object]:
    frontend_url = settings.frontend_url or settings.server_public_url
    try:
        frontend = urlparse(frontend_url)
        server = urlparse(settings.server_public_url)
        cross_origin = (frontend.scheme, frontend.netloc) != (server.scheme, server.netloc)
    except Exception:
        cross_origin = False

    if cross_origin:
        return {"secure": True, "samesite": "none"}

    return {
        "secure": settings.server_public_url.lower().startswith("https://"),
        "samesite": "lax",
    }


def _sanitize_return_to(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    return candidate


def _oidc_client(settings: Settings, provider: str):
    if provider != "oidc":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if not settings.oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is disabled")

    oauth = OAuth()
    oauth.register(
        name="oidc",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value()
        if settings.oidc_client_secret
        else None,
        server_metadata_url=f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={"scope": " ".join(settings.oidc_scopes)},
    )
    return oauth.create_client("oidc")


def _set_oidc_cookie(response: Response, settings: Settings, name: str, value: str) -> None:
    params = _resolve_cookie_params(settings)
    response.set_cookie(
        key=name,
        value=value,
        max_age=600,
        path="/",
        domain=settings.session_cookie_domain,
        httponly=True,
        secure=bool(params["secure"]),
        samesite=str(params["samesite"]),
    )


def _clear_oidc_cookies(response: Response, settings: Settings) -> None:
    params = _resolve_cookie_params(settings)
    expired_at = utc_now() - timedelta(days=1)
    for name in ("ade_oidc_state", "ade_oidc_return_to"):
        response.set_cookie(
            key=name,
            value="",
            max_age=0,
            expires=expired_at,
            path="/",
            domain=settings.session_cookie_domain,
            httponly=True,
            secure=bool(params["secure"]),
            samesite=str(params["samesite"]),
        )


def _redirect_error(settings: Settings, *, code: str) -> RedirectResponse:
    frontend = settings.frontend_url or settings.server_public_url
    return RedirectResponse(f"{frontend}/login?error={quote(code)}")


def _redirect_success(settings: Settings, *, return_to: str) -> RedirectResponse:
    frontend = settings.frontend_url or settings.server_public_url
    return RedirectResponse(f"{frontend}/auth/callback?return_to={quote(return_to)}")


@router.get("/oidc/{provider}/authorize")
def authorize_oidc(
    provider: str,
    return_to: Annotated[str | None, Query()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> Response:
    settings = settings or get_settings()
    client = _oidc_client(settings, provider)

    state = secrets.token_urlsafe(32)
    target = _sanitize_return_to(return_to) or "/"

    authorization_url, _ = client.create_authorization_url(
        redirect_uri=settings.oidc_redirect_url,
        state=state,
    )

    response = RedirectResponse(authorization_url)
    _set_oidc_cookie(response, settings, "ade_oidc_state", state)
    _set_oidc_cookie(response, settings, "ade_oidc_return_to", target)
    return response


@router.get("/oidc/{provider}/callback")
async def callback_oidc(
    provider: str,
    request: Request,
    password_helper: Annotated[PasswordHelper, Depends(get_password_helper)],
    settings: Annotated[Settings, Depends(get_settings)] = None,
    response_mode: Annotated[str | None, Query()] = None,
) -> Response:
    settings = settings or get_settings()

    if not settings.oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is disabled")

    state = request.query_params.get("state")
    code = request.query_params.get("code")
    cookie_state = request.cookies.get("ade_oidc_state")

    if not state or not code or not cookie_state or state != cookie_state:
        return _redirect_error(settings, code="invalid_state")

    return_to = _sanitize_return_to(request.cookies.get("ade_oidc_return_to")) or "/"
    client = _oidc_client(settings, provider)

    try:
        token = await client.fetch_token(
            url=client.metadata["token_endpoint"],
            grant_type="authorization_code",
            code=code,
            redirect_uri=settings.oidc_redirect_url,
        )
    except Exception:
        return _redirect_error(settings, code="token_exchange_failed")

    claims = None
    if token.get("id_token"):
        try:
            claims = client.parse_id_token(token)
        except Exception:
            claims = None

    if not claims:
        try:
            claims = await client.userinfo(token=token)
        except Exception:
            claims = None

    if not claims:
        return _redirect_error(settings, code="missing_identity")

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip() or None

    if not subject:
        return _redirect_error(settings, code="missing_subject")

    session_factory = get_sessionmaker(request)

    class _OidcProvisionError(Exception):
        def __init__(self, code: str) -> None:
            super().__init__(code)
            self.code = code

    def _resolve_user() -> User:
        with session_factory() as session:
            with session.begin():
                stmt = (
                    select(OAuthAccount)
                    .where(OAuthAccount.oauth_name == provider, OAuthAccount.account_id == subject)
                    .limit(1)
                )
                account = session.execute(stmt).scalar_one_or_none()

                if account is not None:
                    user = session.get(User, account.user_id)
                    if user is None:
                        raise _OidcProvisionError("unknown_user")
                else:
                    if not settings.auth_sso_auto_provision or not email:
                        raise _OidcProvisionError("auto_provision_disabled")

                    random_password = secrets.token_urlsafe(32)
                    user = User(
                        email=email,
                        hashed_password=password_helper.hash(random_password),
                        display_name=None,
                        is_active=True,
                        is_superuser=False,
                        is_verified=True,
                        is_service_account=False,
                        last_login_at=utc_now(),
                        failed_login_count=0,
                        locked_until=None,
                    )
                    session.add(user)
                    session.flush()

                    account = OAuthAccount(
                        user_id=user.id,
                        oauth_name=provider,
                        account_id=subject,
                        account_email=email,
                        access_token=token.get("access_token", ""),
                        refresh_token=token.get("refresh_token"),
                        expires_at=_normalize_expires(token.get("expires_at")),
                    )
                    session.add(account)

                account.access_token = token.get("access_token", "")
                account.refresh_token = token.get("refresh_token")
                account.expires_at = _normalize_expires(token.get("expires_at"))
                if email:
                    account.account_email = email
                user.last_login_at = utc_now()
                session.flush()
                return user

    try:
        user = await run_in_threadpool(_resolve_user)
    except _OidcProvisionError as exc:
        return _redirect_error(settings, code=exc.code)

    access_token_db = SyncAccessTokenDatabase(get_sessionmaker(request), AccessToken)
    strategy = DatabaseStrategy(
        access_token_db,
        lifetime_seconds=int(settings.session_access_ttl.total_seconds()),
    )
    token = await strategy.write_token(user)

    accept = request.headers.get("accept", "")
    wants_json = response_mode == "json" or "application/json" in accept
    if wants_json:
        response = JSONResponse({"ok": True})
    else:
        response = _redirect_success(settings, return_to=return_to)

    cookie_transport = get_cookie_transport(settings)
    cookie_transport._set_login_cookie(response, token)
    set_csrf_cookie(response, settings)
    _clear_oidc_cookies(response, settings)
    return response


def _normalize_expires(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


__all__ = ["router"]
