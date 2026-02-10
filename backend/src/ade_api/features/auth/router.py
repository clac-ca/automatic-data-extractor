"""HTTP interface for ADE-owned authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ade_api.api.deps import get_auth_service_read
from ade_api.core.auth import AuthenticatedPrincipal
from ade_api.core.http import (
    clear_session_cookie,
    get_current_principal,
    require_authenticated,
    require_csrf,
    set_session_cookie,
)
from ade_api.core.http.csrf import clear_csrf_cookie, set_csrf_cookie
from ade_api.db import get_db_write
from ade_api.settings import Settings, get_settings
from ade_db.models import User

from ..authn.schemas import (
    AuthLoginMfaRequired,
    AuthLoginRequest,
    AuthLoginSuccess,
    AuthMfaChallengeVerifyRequest,
    AuthMfaEnrollConfirmRequest,
    AuthMfaEnrollConfirmResponse,
    AuthMfaEnrollStartResponse,
    AuthMfaRecoveryRegenerateRequest,
    AuthMfaStatusResponse,
    AuthPasswordChangeRequest,
    AuthPasswordForgotRequest,
    AuthPasswordResetRequest,
)
from ..authn.service import AuthnService, LoginError, MfaRequiredError
from .schemas import (
    AuthProviderListResponse,
    AuthSetupRequest,
    AuthSetupStatusResponse,
)
from .service import AuthService, SetupAlreadyCompletedError
from .sso_router import router as sso_router


def create_auth_router() -> APIRouter:
    router = APIRouter(tags=["auth"])
    router.include_router(sso_router, prefix="", tags=["auth"])

    @router.get(
        "/setup",
        response_model=AuthSetupStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Return setup status for the first admin user",
    )
    def get_setup_status(
        service: Annotated[AuthService, Depends(get_auth_service_read)],
    ) -> AuthSetupStatusResponse:
        return service.get_setup_status()

    @router.post(
        "/setup",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Create the first admin user and log them in",
    )
    async def complete_setup(
        payload: AuthSetupRequest,
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        from ade_api.db import get_session_factory
        from ade_api.features.authn.service import AuthnService

        try:
            session_factory = get_session_factory(request)

            def _create_admin_and_session() -> tuple[User, str]:
                with session_factory() as session:
                    with session.begin():
                        local_service = AuthService(session=session, settings=settings)
                        user = local_service.create_first_admin(payload)
                        authn = AuthnService(session=session, settings=settings)
                        token = authn.create_session(user_id=user.id, auth_method="password")
                        return user, token

            _user, token = await run_in_threadpool(_create_admin_and_session)
        except SetupAlreadyCompletedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        set_session_cookie(response, settings, token)
        set_csrf_cookie(response, settings)
        return response

    @router.get(
        "/providers",
        response_model=AuthProviderListResponse,
        status_code=status.HTTP_200_OK,
        summary="Return configured authentication providers",
    )
    def list_auth_providers(
        service: Annotated[AuthService, Depends(get_auth_service_read)],
    ) -> AuthProviderListResponse:
        payload = service.list_auth_providers()
        provider_items = []
        for item in payload.providers:
            if item.type == "oidc":
                provider_items.append(
                    item.model_copy(update={"start_url": "/api/v1/auth/sso/authorize"})
                )
            else:
                provider_items.append(item.model_copy(update={"start_url": "/api/v1/auth/login"}))
        return AuthProviderListResponse(
            providers=provider_items,
            mode=payload.mode,
            password_reset_enabled=payload.password_reset_enabled,
        )

    @router.post(
        "/login",
        response_model=AuthLoginSuccess | AuthLoginMfaRequired,
        status_code=status.HTTP_200_OK,
        summary="Authenticate with local username/password",
    )
    def login_local(
        payload: AuthLoginRequest,
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response | AuthLoginMfaRequired:
        service = AuthnService(session=db, settings=settings)
        try:
            login_result = service.login_local(
                email=str(payload.email),
                password=payload.password.get_secret_value(),
            )
        except MfaRequiredError as exc:
            return AuthLoginMfaRequired(challenge_token=exc.challenge_token)
        except LoginError as exc:
            # Failed-login counters/lockouts must be persisted even when returning 401.
            db.commit()
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        response = Response(
            content=AuthLoginSuccess(
                mfa_setup_recommended=login_result.mfa_setup_recommended,
                mfa_setup_required=login_result.mfa_setup_required,
                password_change_required=login_result.password_change_required,
            ).model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
        set_session_cookie(response, settings, login_result.session_token)
        set_csrf_cookie(response, settings)
        return response

    @router.post(
        "/logout",
        dependencies=[Depends(require_csrf)],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Logout current user and revoke their sessions",
    )
    def logout_local(
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.revoke_all_sessions_for_user(user_id=user.id)
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        clear_session_cookie(response, settings)
        clear_csrf_cookie(response, settings)
        return response

    @router.post(
        "/password/forgot",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Create a password reset token and schedule delivery",
    )
    def password_forgot(
        payload: AuthPasswordForgotRequest,
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.forgot_password(email=str(payload.email))
        return Response(status_code=status.HTTP_202_ACCEPTED)

    @router.post(
        "/password/reset",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Consume a password reset token and update credentials",
    )
    def password_reset(
        payload: AuthPasswordResetRequest,
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.reset_password(
            token=payload.token.get_secret_value(),
            new_password=payload.new_password.get_secret_value(),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/password/change",
        dependencies=[Depends(require_csrf)],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Change password for the current authenticated user",
    )
    def password_change(
        payload: AuthPasswordChangeRequest,
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.change_password(
            user=user,
            current_password=payload.current_password.get_secret_value(),
            new_password=payload.new_password.get_secret_value(),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/mfa/totp/enroll/start",
        dependencies=[Depends(require_csrf)],
        response_model=AuthMfaEnrollStartResponse,
        status_code=status.HTTP_200_OK,
        summary="Start TOTP MFA enrollment for the current user",
    )
    def mfa_enroll_start(
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> AuthMfaEnrollStartResponse:
        service = AuthnService(session=db, settings=settings)
        uri, issuer, account_name = service.start_totp_enrollment(user=user)
        return AuthMfaEnrollStartResponse(
            otpauth_uri=uri,
            issuer=issuer,
            account_name=account_name,
        )

    @router.get(
        "/mfa/totp",
        response_model=AuthMfaStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Read TOTP MFA status for the current user",
    )
    def mfa_status(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> AuthMfaStatusResponse:
        service = AuthnService(session=db, settings=settings)
        enabled, enrolled_at, recovery_codes_remaining = service.get_totp_status(user=user)
        onboarding_recommended, onboarding_required, skip_allowed = service.totp_onboarding_flags(
            has_mfa_enabled=enabled,
            auth_via=principal.auth_via,
            session_auth_method=principal.session_auth_method,
        )
        return AuthMfaStatusResponse(
            enabled=enabled,
            enrolled_at=enrolled_at,
            recovery_codes_remaining=recovery_codes_remaining,
            onboarding_recommended=onboarding_recommended,
            onboarding_required=onboarding_required,
            skip_allowed=skip_allowed,
        )

    @router.post(
        "/mfa/totp/enroll/confirm",
        dependencies=[Depends(require_csrf)],
        response_model=AuthMfaEnrollConfirmResponse,
        status_code=status.HTTP_200_OK,
        summary="Confirm TOTP enrollment with current code",
    )
    def mfa_enroll_confirm(
        payload: AuthMfaEnrollConfirmRequest,
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> AuthMfaEnrollConfirmResponse:
        service = AuthnService(session=db, settings=settings)
        recovery_codes = service.confirm_totp_enrollment(user=user, code=payload.code)
        return AuthMfaEnrollConfirmResponse(recovery_codes=recovery_codes)

    @router.post(
        "/mfa/totp/recovery/regenerate",
        dependencies=[Depends(require_csrf)],
        response_model=AuthMfaEnrollConfirmResponse,
        status_code=status.HTTP_200_OK,
        summary="Regenerate recovery codes for current user",
    )
    def mfa_regenerate_recovery_codes(
        payload: AuthMfaRecoveryRegenerateRequest,
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> AuthMfaEnrollConfirmResponse:
        service = AuthnService(session=db, settings=settings)
        recovery_codes = service.regenerate_recovery_codes(user=user, code=payload.code)
        return AuthMfaEnrollConfirmResponse(recovery_codes=recovery_codes)

    @router.post(
        "/mfa/challenge/verify",
        response_model=AuthLoginSuccess,
        status_code=status.HTTP_200_OK,
        summary="Verify MFA challenge and issue a session",
    )
    def mfa_verify_challenge(
        payload: AuthMfaChallengeVerifyRequest,
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        login_result = service.verify_challenge(
            challenge_token=payload.challenge_token,
            code=payload.code,
        )
        response = Response(
            content=AuthLoginSuccess(
                mfa_setup_recommended=login_result.mfa_setup_recommended,
                mfa_setup_required=login_result.mfa_setup_required,
                password_change_required=login_result.password_change_required,
            ).model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
        set_session_cookie(response, settings, login_result.session_token)
        set_csrf_cookie(response, settings)
        return response

    @router.delete(
        "/mfa/totp",
        dependencies=[Depends(require_csrf)],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Disable TOTP for the current user",
    )
    def mfa_disable(
        user: Annotated[User, Security(require_authenticated)],
        db: Annotated[Session, Depends(get_db_write)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.disable_totp(user=user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


__all__ = ["create_auth_router"]
