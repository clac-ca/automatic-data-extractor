"""HTTP interface for ADE-owned authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, status
from fastapi.concurrency import run_in_threadpool

from ade_api.api.deps import get_auth_service_read
from ade_api.core.http import (
    clear_session_cookie,
    require_authenticated,
    require_csrf,
    set_session_cookie,
)
from ade_api.core.http.csrf import clear_csrf_cookie, set_csrf_cookie
from ade_api.db import get_db_write
from ade_api.settings import Settings
from ade_db.models import User

from ..authn.schemas import (
    AuthLoginMfaRequired,
    AuthLoginRequest,
    AuthLoginSuccess,
    AuthMfaChallengeVerifyRequest,
    AuthMfaEnrollConfirmRequest,
    AuthMfaEnrollConfirmResponse,
    AuthMfaEnrollStartResponse,
    AuthPasswordForgotRequest,
    AuthPasswordResetRequest,
)
from ..authn.service import AuthnService, LoginError, MfaRequiredError
from .schemas import AuthProviderListResponse, AuthSetupRequest, AuthSetupStatusResponse
from .service import AuthService, SetupAlreadyCompletedError
from .sso_router import router as sso_router


def create_auth_router(settings: Settings) -> APIRouter:
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
    ) -> Response:
        from ade_api.core.security import hash_password
        from ade_api.db import get_session_factory
        from ade_api.features.authn.service import AuthnService

        password_hash = hash_password(payload.password.get_secret_value())

        try:
            session_factory = get_session_factory(request)

            def _create_admin_and_session() -> tuple[User, str]:
                with session_factory() as session:
                    with session.begin():
                        local_service = AuthService(session=session, settings=settings)
                        user = local_service.create_first_admin(
                            payload,
                            password_hash=password_hash,
                        )
                        authn = AuthnService(session=session, settings=settings)
                        token = authn.create_session(user_id=user.id)
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
        return AuthProviderListResponse(providers=provider_items, force_sso=payload.force_sso)

    @router.post(
        "/login",
        response_model=AuthLoginSuccess | AuthLoginMfaRequired,
        status_code=status.HTTP_200_OK,
        summary="Authenticate with local username/password",
    )
    def login_local(
        payload: AuthLoginRequest,
        db=Depends(get_db_write),
    ) -> AuthLoginSuccess | AuthLoginMfaRequired:
        service = AuthnService(session=db, settings=settings)
        try:
            session_token = service.login_local(
                email=str(payload.email),
                password=payload.password.get_secret_value(),
            )
        except MfaRequiredError as exc:
            return AuthLoginMfaRequired(challengeToken=exc.challenge_token)
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
            content=AuthLoginSuccess().model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
        set_session_cookie(response, settings, session_token)
        set_csrf_cookie(response, settings)
        return response  # type: ignore[return-value]

    @router.post(
        "/logout",
        dependencies=[Depends(require_csrf)],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Logout current user and revoke their sessions",
    )
    def logout_local(
        user: Annotated[User, Security(require_authenticated)],
        db=Depends(get_db_write),
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
        db=Depends(get_db_write),
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
        db=Depends(get_db_write),
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.reset_password(
            token=payload.token.get_secret_value(),
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
        db=Depends(get_db_write),
    ) -> AuthMfaEnrollStartResponse:
        service = AuthnService(session=db, settings=settings)
        uri, issuer, account_name = service.start_totp_enrollment(user=user)
        return AuthMfaEnrollStartResponse(
            otpauthUri=uri,
            issuer=issuer,
            accountName=account_name,
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
        db=Depends(get_db_write),
    ) -> AuthMfaEnrollConfirmResponse:
        service = AuthnService(session=db, settings=settings)
        recovery_codes = service.confirm_totp_enrollment(user=user, code=payload.code)
        return AuthMfaEnrollConfirmResponse(recoveryCodes=recovery_codes)

    @router.post(
        "/mfa/challenge/verify",
        response_model=AuthLoginSuccess,
        status_code=status.HTTP_200_OK,
        summary="Verify MFA challenge and issue a session",
    )
    def mfa_verify_challenge(
        payload: AuthMfaChallengeVerifyRequest,
        db=Depends(get_db_write),
    ) -> AuthLoginSuccess:
        service = AuthnService(session=db, settings=settings)
        token = service.verify_challenge(
            challenge_token=payload.challenge_token,
            code=payload.code,
        )
        response = Response(
            content=AuthLoginSuccess().model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
        set_session_cookie(response, settings, token)
        set_csrf_cookie(response, settings)
        return response  # type: ignore[return-value]

    @router.delete(
        "/mfa/totp",
        dependencies=[Depends(require_csrf)],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Disable TOTP for the current user",
    )
    def mfa_disable(
        user: Annotated[User, Security(require_authenticated)],
        db=Depends(get_db_write),
    ) -> Response:
        service = AuthnService(session=db, settings=settings)
        service.disable_totp(user=user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


__all__ = ["create_auth_router"]
