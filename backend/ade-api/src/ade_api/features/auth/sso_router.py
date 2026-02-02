"""OIDC SSO endpoints backed by database-managed provider config."""

from __future__ import annotations
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.logging import log_context
from ade_api.common.rate_limit import InMemoryRateLimiter, RateLimit
from ade_api.common.time import utc_now
from ade_api.common.urls import sanitize_return_to
from ade_api.core.auth.users import get_cookie_transport, get_password_helper
from ade_api.core.http.csrf import set_csrf_cookie
from ade_api.db import get_db_write, get_db_read
from ade_db.models import (
    AccessToken,
    SsoIdentity,
    SsoProvider,
    SsoProviderDomain,
    SsoProviderStatus,
    User,
)
from ade_api.settings import Settings, get_settings

from ade_api.features.sso.schemas import PublicSsoProviderListResponse
from ade_api.features.sso.oidc import (
    OidcDiscoveryError,
    OidcJwksError,
    OidcTokenExchangeError,
    OidcTokenValidationError,
    discover_metadata,
    exchange_code,
    validate_id_token,
)
from ade_api.features.sso.service import AuthStateError, SsoService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sso", tags=["auth"])

_AUTHORIZE_LIMITER = InMemoryRateLimiter(limit=RateLimit(max_requests=30, window_seconds=60))
_CALLBACK_LIMITER = InMemoryRateLimiter(limit=RateLimit(max_requests=30, window_seconds=60))


class ProvisioningError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    id: str
    issuer: str
    client_id: str
    client_secret: str


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept.lower()


def _rate_limit_key(request: Request, provider_id: str, suffix: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{provider_id}:{suffix}"


def _login_redirect(
    settings: Settings,
    *,
    code: str,
    provider_id: str | None = None,
    return_to: str | None = None,
) -> RedirectResponse:
    frontend = settings.frontend_url or settings.server_public_url
    params: dict[str, str] = {"ssoError": code}
    if provider_id:
        params["providerId"] = provider_id
    if return_to:
        params["returnTo"] = return_to
    return RedirectResponse(f"{frontend}/login?{urlencode(params)}")


def _error_response(
    request: Request,
    settings: Settings,
    *,
    code: str,
    provider_id: str | None = None,
    return_to: str | None = None,
) -> Response:
    if _wants_json(request):
        return JSONResponse({"ok": False, "returnTo": None, "error": code})
    return _login_redirect(
        settings,
        code=code,
        provider_id=provider_id,
        return_to=return_to,
    )


def _success_response(
    request: Request,
    settings: Settings,
    *,
    return_to: str,
) -> Response:
    if _wants_json(request):
        return JSONResponse({"ok": True, "returnTo": return_to, "error": None})
    frontend = settings.frontend_url or settings.server_public_url
    return RedirectResponse(f"{frontend}{return_to}")


def _callback_url(settings: Settings, provider_id: str) -> str:
    base = settings.server_public_url.rstrip("/")
    return f"{base}/api/v1/auth/sso/{provider_id}/callback"


def _generate_verifier() -> str:
    while True:
        verifier = secrets.token_urlsafe(64)
        if len(verifier) < 43:
            continue
        if len(verifier) > 128:
            verifier = verifier[:128]
        return verifier


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _resolve_email_verified(claims: dict[str, Any], email: str) -> bool:
    if _coerce_bool(claims.get("email_verified")):
        return True

    verified_primary = claims.get("verified_primary_email")
    if isinstance(verified_primary, str):
        return verified_primary.strip().lower() == email.strip().lower()
    if isinstance(verified_primary, list):
        normalized = email.strip().lower()
        return any(
            isinstance(item, str) and item.strip().lower() == normalized
            for item in verified_primary
        )
    return _coerce_bool(verified_primary)


def _extract_domain(email: str) -> str | None:
    if "@" not in email:
        return None
    _, domain = email.rsplit("@", 1)
    if not domain:
        return None
    lowered = domain.lower()
    try:
        return lowered.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def _provider_domains(session: Session, provider_id: str) -> set[str]:
    stmt = select(SsoProviderDomain.domain).where(SsoProviderDomain.provider_id == provider_id)
    return {domain for domain in session.execute(stmt).scalars()}


def _load_provider_snapshot(
    session: Session,
    *,
    provider_id: str,
    settings: Settings,
) -> ProviderSnapshot:
    service = SsoService(session=session, settings=settings)
    if not service.is_sso_enabled():
        raise ProvisioningError("PROVIDER_DISABLED")

    provider = session.get(SsoProvider, provider_id)
    if provider is None or provider.status == SsoProviderStatus.DELETED:
        raise ProvisioningError("PROVIDER_NOT_FOUND")
    if provider.status != SsoProviderStatus.ACTIVE:
        raise ProvisioningError("PROVIDER_DISABLED")
    if not provider.issuer or not provider.client_id or not provider.client_secret_enc:
        raise ProvisioningError("PROVIDER_MISCONFIGURED")
    try:
        client_secret = service.decrypt_client_secret(provider)
    except ValueError as exc:
        raise ProvisioningError("PROVIDER_MISCONFIGURED") from exc

    return ProviderSnapshot(
        id=provider.id,
        issuer=provider.issuer,
        client_id=provider.client_id,
        client_secret=client_secret,
    )


def _persist_auth_state(
    session: Session,
    *,
    settings: Settings,
    state: str,
    provider_id: str,
    nonce: str,
    verifier: str,
    return_to: str,
) -> None:
    service = SsoService(session=session, settings=settings)
    service.create_auth_state(
        state=state,
        provider_id=provider_id,
        nonce=nonce,
        pkce_verifier=verifier,
        return_to=return_to,
    )


def _consume_auth_state(
    session: Session,
    *,
    settings: Settings,
    state: str,
    provider_id: str,
) -> dict[str, str]:
    service = SsoService(session=session, settings=settings)
    record = service.consume_auth_state(state=state, provider_id=provider_id)
    return {
        "nonce": record.nonce,
        "pkce_verifier": record.pkce_verifier,
        "return_to": record.return_to,
    }


def _resolve_user(
    session: Session,
    *,
    settings: Settings,
    password_helper: PasswordHelper,
    provider_id: str,
    subject: str,
    email: str,
    email_verified: bool,
) -> User:
    identity = session.execute(
        select(SsoIdentity)
        .where(SsoIdentity.provider_id == provider_id)
        .where(SsoIdentity.subject == subject)
        .limit(1)
    ).scalar_one_or_none()

    if identity is not None:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active or user.is_service_account:
            raise ProvisioningError("USER_NOT_ALLOWED")
        identity.email = email
        identity.email_verified = email_verified
        user.last_login_at = utc_now()
        logger.info(
            "sso.user.resolve.identity",
            extra=log_context(provider_id=provider_id, user_id=str(user.id)),
        )
        return user

    if not email_verified:
        raise ProvisioningError("EMAIL_NOT_VERIFIED")

    canonical_email = email.strip().lower()
    user = session.execute(
        select(User).where(User.email_normalized == canonical_email).limit(1)
    ).scalar_one_or_none()

    if user is not None:
        if not user.is_active or user.is_service_account:
            raise ProvisioningError("USER_NOT_ALLOWED")
        existing_for_user = session.execute(
            select(SsoIdentity)
            .where(SsoIdentity.provider_id == provider_id)
            .where(SsoIdentity.user_id == user.id)
            .limit(1)
        ).scalar_one_or_none()
        if existing_for_user is not None:
            raise ProvisioningError("IDENTITY_CONFLICT")
        identity = SsoIdentity(
            provider_id=provider_id,
            subject=subject,
            user_id=user.id,
            email=canonical_email,
            email_verified=email_verified,
        )
        session.add(identity)
        user.last_login_at = utc_now()
        logger.info(
            "sso.user.resolve.email_link",
            extra=log_context(provider_id=provider_id, user_id=str(user.id)),
        )
        return user

    if not settings.auth_sso_auto_provision:
        raise ProvisioningError("AUTO_PROVISION_DISABLED")

    domain = _extract_domain(canonical_email)
    if not domain:
        raise ProvisioningError("DOMAIN_NOT_ALLOWED")
    allowed_domains = _provider_domains(session, provider_id)
    if not allowed_domains or domain not in allowed_domains:
        raise ProvisioningError("DOMAIN_NOT_ALLOWED")

    random_password = secrets.token_urlsafe(32)
    user = User(
        email=canonical_email,
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

    identity = SsoIdentity(
        provider_id=provider_id,
        subject=subject,
        user_id=user.id,
        email=canonical_email,
        email_verified=email_verified,
    )
    session.add(identity)
    logger.info(
        "sso.user.resolve.auto_provision",
        extra=log_context(provider_id=provider_id, user_id=str(user.id)),
    )
    return user


def _issue_session_token(session: Session, *, user: User) -> str:
    token = secrets.token_urlsafe()
    session.add(AccessToken(user_id=user.id, token=token))
    return token


@router.get(
    "/providers",
    response_model=PublicSsoProviderListResponse,
    status_code=status.HTTP_200_OK,
    summary="Return active SSO providers",
)
def list_sso_providers(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db_read)] = None,
) -> PublicSsoProviderListResponse:
    settings = settings or get_settings()
    service = SsoService(session=db, settings=settings)
    providers = service.list_active_providers()
    items = [
        {
            "id": provider.id,
            "label": provider.label,
            "type": "oidc",
            "startUrl": f"/api/v1/auth/sso/{provider.id}/authorize",
        }
        for provider in providers
    ]
    return PublicSsoProviderListResponse(
        providers=items,
        force_sso=bool(settings.auth_force_sso),
    )


@router.get("/{providerId}/authorize")
def authorize_sso(
    provider_id: Annotated[str, Path(alias="providerId")],
    request: Request,
    return_to: Annotated[str | None, Query(alias="returnTo")] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db_write)] = None,
) -> Response:
    settings = settings or get_settings()
    if not _AUTHORIZE_LIMITER.allow(_rate_limit_key(request, provider_id, "authorize")):
        return _error_response(
            request,
            settings,
            code="RATE_LIMITED",
            provider_id=provider_id,
        )

    sanitized_return_to = sanitize_return_to(return_to) or "/"

    try:
        provider = _load_provider_snapshot(
            db,
            provider_id=provider_id,
            settings=settings,
        )
    except ProvisioningError as exc:
        return _error_response(
            request,
            settings,
            code=exc.code,
            provider_id=provider_id,
            return_to=sanitized_return_to,
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = _generate_verifier()
    challenge = _code_challenge(verifier)

    _persist_auth_state(
        db,
        settings=settings,
        state=state,
        provider_id=provider.id,
        nonce=nonce,
        verifier=verifier,
        return_to=sanitized_return_to,
    )
    db.commit()

    with httpx.Client() as client:
        try:
            metadata = discover_metadata(provider.issuer, client)
        except OidcDiscoveryError:
            return _error_response(
                request,
                settings,
                code="PROVIDER_MISCONFIGURED",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )

    params = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": _callback_url(settings, provider.id),
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{metadata.authorization_endpoint}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/{providerId}/callback")
def callback_sso(
    provider_id: Annotated[str, Path(alias="providerId")],
    request: Request,
    password_helper: Annotated[PasswordHelper, Depends(get_password_helper)],
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db_write)] = None,
) -> Response:
    settings = settings or get_settings()
    try:
        if not _CALLBACK_LIMITER.allow(_rate_limit_key(request, provider_id, "callback")):
            return _error_response(request, settings, code="RATE_LIMITED", provider_id=provider_id)

        if request.query_params.get("error"):
            logger.warning(
                "sso.callback.upstream_error",
                extra=log_context(provider_id=provider_id),
            )
            return _error_response(request, settings, code="UPSTREAM_ERROR", provider_id=provider_id)

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return _error_response(request, settings, code="STATE_INVALID", provider_id=provider_id)

        try:
            state_record = _consume_auth_state(
                db,
                settings=settings,
                state=state,
                provider_id=provider_id,
            )
        except AuthStateError as exc:
            return _error_response(
                request,
                settings,
                code=exc.code,
                provider_id=provider_id,
            )
        db.commit()

        sanitized_return_to = sanitize_return_to(state_record.get("return_to")) or "/"

        try:
            provider = _load_provider_snapshot(
                db,
                provider_id=provider_id,
                settings=settings,
            )
        except ProvisioningError as exc:
            return _error_response(
                request,
                settings,
                code=exc.code,
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )

        with httpx.Client() as client:
            try:
                metadata = discover_metadata(provider.issuer, client)
            except OidcDiscoveryError:
                return _error_response(
                    request,
                    settings,
                    code="PROVIDER_MISCONFIGURED",
                    provider_id=provider_id,
                    return_to=sanitized_return_to,
                )

            try:
                token_response = exchange_code(
                    token_endpoint=metadata.token_endpoint,
                    client_id=provider.client_id,
                    client_secret=provider.client_secret,
                    code=code,
                    redirect_uri=_callback_url(settings, provider.id),
                    code_verifier=state_record["pkce_verifier"],
                    client=client,
                )
            except OidcTokenExchangeError:
                return _error_response(
                    request,
                    settings,
                    code="TOKEN_EXCHANGE_FAILED",
                    provider_id=provider_id,
                    return_to=sanitized_return_to,
                )

        try:
            claims = validate_id_token(
                token=token_response["id_token"],
                issuer=metadata.issuer,
                client_id=provider.client_id,
                nonce=state_record["nonce"],
                jwks_uri=metadata.jwks_uri,
                now=utc_now(),
            )
        except OidcJwksError:
            return _error_response(
                request,
                settings,
                code="PROVIDER_MISCONFIGURED",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )
        except OidcTokenValidationError:
            return _error_response(
                request,
                settings,
                code="ID_TOKEN_INVALID",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )

        subject = str(claims.get("sub") or "").strip()
        if not subject:
            return _error_response(
                request,
                settings,
                code="ID_TOKEN_INVALID",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )

        email = str(claims.get("email") or "").strip()
        if not email:
            return _error_response(
                request,
                settings,
                code="EMAIL_MISSING",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )
        email_verified = _resolve_email_verified(claims, email)

        try:
            user = _resolve_user(
                db,
                settings=settings,
                password_helper=password_helper,
                provider_id=provider_id,
                subject=subject,
                email=email,
                email_verified=email_verified,
            )
        except IntegrityError:
            db.rollback()
            return _error_response(
                request,
                settings,
                code="IDENTITY_CONFLICT",
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )
        except ProvisioningError as exc:
            db.rollback()
            return _error_response(
                request,
                settings,
                code=exc.code,
                provider_id=provider_id,
                return_to=sanitized_return_to,
            )

        logger.info(
            "sso.callback.success",
            extra=log_context(provider_id=provider_id, user_id=str(user.id)),
        )

        session_token = _issue_session_token(db, user=user)
        db.commit()

        response = _success_response(request, settings, return_to=sanitized_return_to)
        cookie_transport = get_cookie_transport(settings)
        cookie_transport._set_login_cookie(response, session_token)
        set_csrf_cookie(response, settings)
        return response
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception(
            "sso.callback.internal_error",
            extra=log_context(provider_id=provider_id),
        )
        return _error_response(
            request,
            settings,
            code="INTERNAL_ERROR",
            provider_id=provider_id,
        )


__all__ = ["router"]
