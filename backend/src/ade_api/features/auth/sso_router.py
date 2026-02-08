"""Single-provider OIDC SSO endpoints."""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.logging import log_context
from ade_api.common.rate_limit import InMemoryRateLimiter, RateLimit
from ade_api.common.responses import JSONResponse
from ade_api.common.time import utc_now
from ade_api.common.urls import sanitize_return_to
from ade_api.core.http.csrf import set_csrf_cookie
from ade_api.core.http.session_cookie import set_session_cookie
from ade_api.core.security import hash_password, mint_opaque_token
from ade_api.db import get_db_read, get_db_write
from ade_api.features.authn.service import AuthnService
from ade_api.features.sso.oidc import (
    OidcDiscoveryError,
    OidcJwksError,
    OidcTokenExchangeError,
    OidcTokenValidationError,
    discover_metadata,
    exchange_code,
    validate_id_token,
)
from ade_api.features.sso.schemas import PublicSsoProviderListResponse
from ade_api.features.sso.service import AuthStateError, SsoService
from ade_api.settings import Settings, get_settings
from ade_db.models import SsoIdentity, SsoProvider, SsoProviderDomain, SsoProviderStatus, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sso", tags=["auth"])

_AUTHORIZE_LIMITER = InMemoryRateLimiter(limit=RateLimit(max_requests=30, window_seconds=60))
_CALLBACK_LIMITER = InMemoryRateLimiter(limit=RateLimit(max_requests=30, window_seconds=60))


class ProvisioningError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept.lower()


def _rate_limit_key(request: Request, suffix: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:sso:{suffix}"


def _login_redirect(
    settings: Settings,
    *,
    code: str,
    return_to: str | None = None,
) -> RedirectResponse:
    frontend = settings.public_web_url
    params: dict[str, str] = {"ssoError": code}
    if return_to:
        params["returnTo"] = return_to
    return RedirectResponse(f"{frontend}/login?{urlencode(params)}")


def _error_response(
    request: Request,
    settings: Settings,
    *,
    code: str,
    return_to: str | None = None,
) -> Response:
    if _wants_json(request):
        return JSONResponse({"ok": False, "returnTo": None, "error": code})
    return _login_redirect(
        settings,
        code=code,
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
    frontend = settings.public_web_url
    return RedirectResponse(f"{frontend}{return_to}")


def _callback_url(settings: Settings) -> str:
    base = settings.public_web_url.rstrip("/")
    return f"{base}/api/v1/auth/sso/callback"


def _generate_verifier() -> str:
    while True:
        verifier = mint_opaque_token(64)
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
    from sqlalchemy import select

    stmt = select(SsoProviderDomain.domain).where(SsoProviderDomain.provider_id == provider_id)
    return {domain for domain in session.execute(stmt).scalars()}


def _load_provider_snapshot(session: Session, settings: Settings) -> tuple[SsoProvider, str]:
    authn = AuthnService(session=session, settings=settings)
    policy = authn.get_policy()
    if not policy.external_enabled:
        raise ProvisioningError("PROVIDER_DISABLED")
    provider = authn.get_external_provider()
    if provider is None or provider.status == SsoProviderStatus.DELETED:
        raise ProvisioningError("PROVIDER_NOT_FOUND")
    if provider.status != SsoProviderStatus.ACTIVE:
        raise ProvisioningError("PROVIDER_DISABLED")
    if not provider.issuer or not provider.client_id or not provider.client_secret_enc:
        raise ProvisioningError("PROVIDER_MISCONFIGURED")
    try:
        secret = SsoService(session=session, settings=settings).decrypt_client_secret(provider)
    except ValueError as exc:
        raise ProvisioningError("PROVIDER_MISCONFIGURED") from exc
    return provider, secret


def _resolve_user(
    session: Session,
    *,
    settings: Settings,
    provider_id: str,
    subject: str,
    email: str,
    email_verified: bool,
) -> User:
    from sqlalchemy import select

    identity = session.execute(
        select(SsoIdentity)
        .where(SsoIdentity.provider_id == provider_id)
        .where(SsoIdentity.subject == subject)
        .limit(1)
    ).scalar_one_or_none()

    if identity is not None:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active:
            raise ProvisioningError("USER_NOT_ALLOWED")
        identity.email = email
        identity.email_verified = email_verified
        user.last_login_at = utc_now()
        return user

    if not email_verified:
        raise ProvisioningError("EMAIL_NOT_VERIFIED")

    canonical_email = email.strip().lower()
    user = session.execute(
        select(User).where(User.email_normalized == canonical_email).limit(1)
    ).scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            raise ProvisioningError("USER_NOT_ALLOWED")
        existing_for_user = session.execute(
            select(SsoIdentity)
            .where(SsoIdentity.provider_id == provider_id)
            .where(SsoIdentity.user_id == user.id)
            .limit(1)
        ).scalar_one_or_none()
        if existing_for_user is not None:
            raise ProvisioningError("IDENTITY_CONFLICT")
        session.add(
            SsoIdentity(
                provider_id=provider_id,
                subject=subject,
                user_id=user.id,
                email=canonical_email,
                email_verified=email_verified,
            )
        )
        user.last_login_at = utc_now()
        return user

    authn = AuthnService(session=session, settings=settings)
    if not authn.get_policy().allow_jit_provisioning:
        raise ProvisioningError("AUTO_PROVISION_DISABLED")

    domain = _extract_domain(canonical_email)
    if not domain:
        raise ProvisioningError("DOMAIN_NOT_ALLOWED")
    allowed_domains = _provider_domains(session, provider_id)
    if allowed_domains and domain not in allowed_domains:
        raise ProvisioningError("DOMAIN_NOT_ALLOWED")

    user = User(
        email=canonical_email,
        hashed_password=hash_password(mint_opaque_token(32)),
        display_name=None,
        is_active=True,
        is_verified=True,
        is_service_account=False,
        last_login_at=utc_now(),
        failed_login_count=0,
        locked_until=None,
    )
    session.add(user)
    session.flush()
    session.add(
        SsoIdentity(
            provider_id=provider_id,
            subject=subject,
            user_id=user.id,
            email=canonical_email,
            email_verified=email_verified,
        )
    )
    return user


@router.get(
    "/providers",
    response_model=PublicSsoProviderListResponse,
    status_code=status.HTTP_200_OK,
    summary="Return active SSO providers",
)
def list_sso_providers(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db_read)],
) -> PublicSsoProviderListResponse:
    authn = AuthnService(session=db, settings=settings)
    provider = authn.get_external_provider()
    if provider is None or provider.status != SsoProviderStatus.ACTIVE or not authn.get_policy().external_enabled:
        return PublicSsoProviderListResponse(providers=[], forceSso=authn.get_policy().enforce_sso)
    return PublicSsoProviderListResponse(
        providers=[
            {
                "id": provider.id,
                "label": provider.label,
                "type": "oidc",
                "startUrl": "/api/v1/auth/sso/authorize",
            }
        ],
        forceSso=authn.get_policy().enforce_sso,
    )


@router.get("/authorize")
def authorize_sso(
    request: Request,
    return_to: Annotated[str | None, Query(alias="returnTo")] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db_write)] = None,
) -> Response:
    settings = settings or get_settings()
    if not _AUTHORIZE_LIMITER.allow(_rate_limit_key(request, "authorize")):
        return _error_response(request, settings, code="RATE_LIMITED")

    sanitized_return_to = sanitize_return_to(return_to) or "/"

    try:
        provider, _client_secret = _load_provider_snapshot(db, settings)
    except ProvisioningError as exc:
        return _error_response(request, settings, code=exc.code, return_to=sanitized_return_to)

    state = mint_opaque_token(32)
    nonce = mint_opaque_token(32)
    verifier = _generate_verifier()
    challenge = _code_challenge(verifier)

    SsoService(session=db, settings=settings).create_auth_state(
        state=state,
        provider_id=provider.id,
        nonce=nonce,
        pkce_verifier=verifier,
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
                return_to=sanitized_return_to,
            )

    params = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": _callback_url(settings),
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{metadata.authorization_endpoint}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/callback")
def callback_sso(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db_write)] = None,
) -> Response:
    settings = settings or get_settings()
    try:
        if not _CALLBACK_LIMITER.allow(_rate_limit_key(request, "callback")):
            return _error_response(request, settings, code="RATE_LIMITED")

        if request.query_params.get("error"):
            return _error_response(request, settings, code="UPSTREAM_ERROR")

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return _error_response(request, settings, code="STATE_INVALID")

        try:
            provider, client_secret = _load_provider_snapshot(db, settings)
        except ProvisioningError as exc:
            return _error_response(request, settings, code=exc.code)

        try:
            state_record = SsoService(session=db, settings=settings).consume_auth_state(
                state=state,
                provider_id=provider.id,
            )
        except AuthStateError as exc:
            return _error_response(request, settings, code=exc.code)
        db.commit()

        sanitized_return_to = sanitize_return_to(state_record.return_to) or "/"

        with httpx.Client() as client:
            try:
                metadata = discover_metadata(provider.issuer, client)
            except OidcDiscoveryError:
                return _error_response(
                    request,
                    settings,
                    code="PROVIDER_MISCONFIGURED",
                    return_to=sanitized_return_to,
                )

            try:
                token_response = exchange_code(
                    token_endpoint=metadata.token_endpoint,
                    client_id=provider.client_id,
                    client_secret=client_secret,
                    code=code,
                    redirect_uri=_callback_url(settings),
                    code_verifier=state_record.pkce_verifier,
                    client=client,
                )
            except OidcTokenExchangeError:
                return _error_response(
                    request,
                    settings,
                    code="TOKEN_EXCHANGE_FAILED",
                    return_to=sanitized_return_to,
                )

        try:
            claims = validate_id_token(
                token=token_response["id_token"],
                issuer=metadata.issuer,
                client_id=provider.client_id,
                nonce=state_record.nonce,
                jwks_uri=metadata.jwks_uri,
                now=utc_now(),
            )
        except OidcJwksError:
            return _error_response(
                request,
                settings,
                code="PROVIDER_MISCONFIGURED",
                return_to=sanitized_return_to,
            )
        except OidcTokenValidationError:
            return _error_response(
                request,
                settings,
                code="ID_TOKEN_INVALID",
                return_to=sanitized_return_to,
            )

        subject = str(claims.get("sub") or "").strip()
        if not subject:
            return _error_response(
                request,
                settings,
                code="ID_TOKEN_INVALID",
                return_to=sanitized_return_to,
            )

        email = str(claims.get("email") or "").strip()
        if not email:
            return _error_response(
                request,
                settings,
                code="EMAIL_MISSING",
                return_to=sanitized_return_to,
            )
        email_verified = _resolve_email_verified(claims, email)

        try:
            user = _resolve_user(
                db,
                settings=settings,
                provider_id=provider.id,
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
                return_to=sanitized_return_to,
            )
        except ProvisioningError as exc:
            db.rollback()
            return _error_response(
                request,
                settings,
                code=exc.code,
                return_to=sanitized_return_to,
            )

        logger.info(
            "sso.callback.success",
            extra=log_context(provider_id=provider.id, user_id=str(user.id)),
        )

        session_token = AuthnService(session=db, settings=settings).create_session(
            user_id=user.id,
            auth_method="sso",
        )
        db.commit()

        response = _success_response(request, settings, return_to=sanitized_return_to)
        set_session_cookie(response, settings, session_token)
        set_csrf_cookie(response, settings)
        return response
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception("sso.callback.internal_error")
        return _error_response(request, settings, code="INTERNAL_ERROR")


__all__ = ["router"]
