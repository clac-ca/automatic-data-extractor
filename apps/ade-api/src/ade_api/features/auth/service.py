"""Authentication and session lifecycle logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.time import utc_now
from ade_api.core.auth.errors import AuthenticationError
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia, PrincipalType
from ade_api.core.models.user import User, UserCredential
from ade_api.core.security.hashing import hash_password, verify_password
from ade_api.core.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from ade_api.settings import Settings

from .schemas import (
    AuthProvider,
    AuthProviderListResponse,
    AuthSetupRequest,
    AuthSetupStatusResponse,
)


@dataclass(slots=True)
class SessionTokens:
    """Internal representation of an issued session."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


def _normalize_email(value: str) -> str:
    """Return a canonical representation for email comparisons."""
    return value.strip().lower()


class InvalidCredentialsError(AuthenticationError):
    """Raised when email/password combination is invalid."""


class InactiveUserError(AuthenticationError):
    """Raised when a user is inactive or disabled."""

    def __init__(self, message: str = "User account is inactive.") -> None:
        super().__init__(message)


class AccountLockedError(PermissionError):
    """Raised when a user is temporarily locked due to failed logins."""

    def __init__(self, message: str = "Account is locked. Try again later.") -> None:
        super().__init__(message)


class RefreshTokenError(AuthenticationError):
    """Raised when a refresh token is invalid or cannot be used."""


class SetupAlreadyCompletedError(RuntimeError):
    """Raised when interactive setup is invoked after users already exist."""


class AuthService:
    """Authentication and session lifecycle.

    This service is pure domain logic; HTTP-specific concerns (headers, cookies,
    response models) live in ``features/auth/router.py``.
    """

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def get_setup_status(self) -> AuthSetupStatusResponse:
        """Return whether initial administrator setup is required."""

        result = await self._session.execute(select(func.count(User.id)))
        user_count = int(result.scalar_one() or 0)
        requires_setup = user_count == 0
        return AuthSetupStatusResponse(
            requires_setup=requires_setup,
            has_users=user_count > 0,
        )

    async def complete_initial_setup(self, payload: AuthSetupRequest) -> SessionTokens:
        """Create the first administrator account and return a session."""

        status = await self.get_setup_status()
        if not status.requires_setup:
            raise SetupAlreadyCompletedError("Initial setup has already been completed.")

        email = str(payload.email).strip()
        now = utc_now()

        user = User(
            email=email,
            display_name=(payload.display_name or "").strip() or None,
            is_active=True,
            is_service_account=False,
            last_login_at=now,
            failed_login_count=0,
            locked_until=None,
        )
        self._session.add(user)
        await self._session.flush()

        password_hash = hash_password(payload.password.get_secret_value())
        credential = UserCredential(
            user_id=user.id,
            password_hash=password_hash,
            last_rotated_at=now,
        )
        self._session.add(credential)
        await self._session.flush()

        return self._issue_session_tokens(user=user, issued_at=now)

    async def login_with_password(self, *, email: str, password: str) -> SessionTokens:
        """Authenticate using email/password and return a fresh session."""

        email_canonical = _normalize_email(email)

        result = await self._session.execute(
            select(User).where(User.email_canonical == email_canonical)
        )
        user: User | None = result.scalar_one_or_none()

        if user is None:
            raise InvalidCredentialsError("Invalid credentials.")

        now = utc_now()

        if user.locked_until and user.locked_until > now:
            raise AccountLockedError("Account is locked. Try again later.")

        if not user.is_active:
            raise InactiveUserError()

        hash_ = user.password_hash
        if hash_ is None or not verify_password(password, hash_):
            raise InvalidCredentialsError("Invalid credentials.")

        user.last_login_at = now
        user.failed_login_count = 0
        user.locked_until = None
        await self._session.flush()

        return self._issue_session_tokens(user=user, issued_at=now)

    async def refresh_session(self, *, refresh_token: str) -> SessionTokens:
        """Rotate session tokens using a refresh token."""

        user_id = await self._resolve_refresh_subject(refresh_token)
        user = await self._session.get(User, user_id)

        if user is None:
            raise RefreshTokenError("Refresh token is no longer valid.")

        now = utc_now()

        if not user.is_active:
            raise RefreshTokenError("Refresh token is no longer valid.")

        if user.locked_until and user.locked_until > now:
            raise AccountLockedError("Account is locked. Try again later.")

        user.last_login_at = now
        await self._session.flush()

        return self._issue_session_tokens(user=user, issued_at=now)

    async def logout(self, *, refresh_token: str | None = None) -> None:
        """Terminate a session."""

        # Stateless placeholder: if a persistent session store is introduced,
        # revocation logic belongs here.
        return None

    def list_auth_providers(self) -> AuthProviderListResponse:
        """Return configured auth providers for UI discovery."""

        providers: list[AuthProvider] = []

        if not self._settings.auth_force_sso:
            providers.append(
                AuthProvider(
                    id="password",
                    label="Email & password",
                    type="password",
                    start_url="/api/v1/auth/session",
                )
            )

        if self._settings.oidc_enabled:
            provider_id = "sso"
            providers.append(
                AuthProvider(
                    id=provider_id,
                    label="Single sign-on",
                    type="oidc",
                    start_url=f"/api/v1/auth/sso/{provider_id}/authorize",
                )
            )

        return AuthProviderListResponse(
            providers=providers,
            force_sso=bool(self._settings.auth_force_sso),
        )

    async def start_sso_login(self, *, provider: str, return_to: str | None = None) -> str:
        """Return a redirect URL to start SSO login."""

        if not self._settings.oidc_enabled:
            raise NotImplementedError("SSO / OIDC is not configured.")
        raise NotImplementedError("SSO / OIDC is not implemented yet.")

    async def complete_sso_login(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> SessionTokens:
        """Complete SSO login given an authorization code and state."""

        if not self._settings.oidc_enabled:
            raise NotImplementedError("SSO / OIDC is not configured.")
        raise NotImplementedError("SSO / OIDC is not implemented yet.")

    def _issue_session_tokens(self, *, user: User, issued_at: datetime) -> SessionTokens:
        """Issue access + refresh token pair for the given user."""

        access_delta = self._settings.jwt_access_ttl
        refresh_delta = self._settings.jwt_refresh_ttl

        access_expires_at = issued_at + access_delta
        refresh_expires_at = issued_at + refresh_delta

        secret = self._settings.jwt_secret_value
        algorithm = self._settings.jwt_algorithm
        principal_type = "service_account" if user.is_service_account else "user"
        base_claims = {
            "sub": str(user.id),
            "email": user.email,
            "pt": principal_type,
        }

        access_token = create_access_token(
            payload=base_claims,
            secret=secret,
            algorithm=algorithm,
            ttl_seconds=int(access_delta.total_seconds()),
        )
        refresh_token = create_refresh_token(
            payload=base_claims,
            secret=secret,
            algorithm=algorithm,
            ttl_seconds=int(refresh_delta.total_seconds()),
        )

        return SessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    async def _resolve_refresh_subject(self, token: str) -> UUID:
        """Decode a refresh token and return the subject (user_id)."""

        try:
            payload = decode_token(
                token=token,
                secret=self._settings.jwt_secret_value,
                algorithms=[self._settings.jwt_algorithm],
            )
        except Exception as exc:
            raise RefreshTokenError("Invalid refresh token.") from exc

        token_type = str(payload.get("typ") or "").lower()
        if token_type != "refresh":
            raise RefreshTokenError("Invalid token type for refresh.")

        subject = str(payload.get("sub") or "").strip()
        if not subject:
            raise RefreshTokenError("Refresh token is missing subject.")

        try:
            return UUID(subject)
        except ValueError as exc:
            raise RefreshTokenError("Refresh token subject is invalid.") from exc

    async def resolve_principal_from_access_token(
        self,
        token: str,
    ) -> AuthenticatedPrincipal:
        """Decode an access token and return an AuthenticatedPrincipal."""

        try:
            payload = decode_token(
                token=token,
                secret=self._settings.jwt_secret_value,
                algorithms=[self._settings.jwt_algorithm],
            )
        except Exception as exc:
            raise AuthenticationError("Invalid access token.") from exc

        token_type = str(payload.get("typ") or "").lower()
        if token_type != "access":
            raise AuthenticationError("Access token required.")

        subject = str(payload.get("sub") or "").strip()
        if not subject:
            raise AuthenticationError("Access token is missing subject.")

        principal_type = str(payload.get("pt") or "").lower() or PrincipalType.USER.value
        try:
            user_id = UUID(subject)
        except ValueError as exc:
            raise AuthenticationError("Access token subject is invalid.") from exc

        user = await self._session.get(User, user_id)
        if user is None:
            raise AuthenticationError("Unknown principal")
        if not user.is_active:
            raise AuthenticationError("User account is inactive.")

        try:
            principal_enum = PrincipalType(principal_type)
        except ValueError:
            principal_enum = PrincipalType.USER

        return AuthenticatedPrincipal(
            user_id=user.id,
            principal_type=principal_enum,
            auth_via=AuthVia.SESSION,
            api_key_id=None,
        )
