"""ADE-owned authentication service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.core.auth.principal import AuthVia
from ade_api.core.security import (
    hash_opaque_token,
    hash_password,
    mint_opaque_token,
    verify_password,
)
from ade_api.core.security.password_policy import (
    PasswordComplexityPolicy,
    enforce_password_complexity,
)
from ade_api.core.security.secrets import decrypt_secret, encrypt_secret
from ade_api.features.admin_settings.service import RuntimeSettingsService
from ade_api.features.rbac import RbacService
from ade_api.features.sso.service import SsoService
from ade_api.settings import Settings
from ade_db.models import (
    AuthSession,
    MfaChallenge,
    PasswordResetToken,
    SsoProvider,
    SsoProviderStatus,
    User,
    UserMfaTotp,
)

from .delivery import NoopPasswordResetDelivery, PasswordResetDelivery
from .schemas import AuthPolicyResponse
from .totp import (
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_codes,
    normalize_recovery_code,
    verify_recovery_code,
    verify_totp,
)

MFA_CHALLENGE_TTL = timedelta(minutes=10)
PASSWORD_RESET_TTL = timedelta(minutes=30)


class LoginError(RuntimeError):
    """Raised when login credentials are invalid."""


class MfaRequiredError(RuntimeError):
    """Raised when a login requires MFA challenge completion."""

    def __init__(self, challenge_token: str) -> None:
        super().__init__("mfa_required")
        self.challenge_token = challenge_token


SessionAuthMethod = Literal["password", "sso", "unknown"]


@dataclass(frozen=True, slots=True)
class LocalLoginSuccess:
    """Result payload for successful local logins."""

    session_token: str
    mfa_setup_recommended: bool
    mfa_setup_required: bool
    password_change_required: bool


@dataclass(slots=True)
class AuthnService:
    """Central auth service for local login/session/reset/MFA/policy."""

    session: Session
    settings: Settings
    delivery: PasswordResetDelivery | None = None
    _runtime_settings: RuntimeSettingsService = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.delivery is None:
            self.delivery = NoopPasswordResetDelivery()
        self._runtime_settings = RuntimeSettingsService(
            session=self.session,
        )

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    def get_policy(self) -> AuthPolicyResponse:
        resolved = self._runtime_settings.get_effective_values().auth
        password = resolved.password
        complexity = password.complexity
        lockout = password.lockout
        return AuthPolicyResponse(
            mode=resolved.mode,
            password_reset_enabled=bool(password.reset_enabled),
            password_mfa_required=bool(password.mfa_required),
            password_min_length=int(complexity.min_length),
            password_require_uppercase=bool(complexity.require_uppercase),
            password_require_lowercase=bool(complexity.require_lowercase),
            password_require_number=bool(complexity.require_number),
            password_require_symbol=bool(complexity.require_symbol),
            password_lockout_max_attempts=int(lockout.max_attempts),
            password_lockout_duration_seconds=int(lockout.duration_seconds),
            idp_provisioning_mode=resolved.identity_provider.provisioning_mode,
        )

    # ------------------------------------------------------------------
    # External provider
    # ------------------------------------------------------------------

    def get_external_provider(self) -> SsoProvider | None:
        stmt = (
            select(SsoProvider)
            .where(SsoProvider.status != SsoProviderStatus.DELETED)
            .order_by(SsoProvider.updated_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def set_external_provider(
        self,
        *,
        provider_id: str,
        label: str,
        issuer: str,
        client_id: str,
        client_secret: str,
        status_value: SsoProviderStatus,
        domains: list[str],
    ) -> SsoProvider:
        service = SsoService(session=self.session, settings=self.settings)
        existing = self.get_external_provider()
        if existing is None:
            provider = service.create_provider(
                provider_id=provider_id,
                label=label,
                issuer=issuer,
                client_id=client_id,
                client_secret=client_secret,
                status_value=status_value,
                domains=domains,
            )
        else:
            provider = service.update_provider(
                existing.id,
                label=label,
                issuer=issuer,
                client_id=client_id,
                client_secret=client_secret,
                status_value=status_value,
                domains=domains,
            )

        # Keep exactly one non-deleted provider.
        stale_stmt = (
            select(SsoProvider.id)
            .where(SsoProvider.id != provider.id)
            .where(SsoProvider.status != SsoProviderStatus.DELETED)
        )
        for stale_id in self.session.execute(stale_stmt).scalars().all():
            service.delete_provider(stale_id)

        return provider

    # ------------------------------------------------------------------
    # Sessions / Login
    # ------------------------------------------------------------------

    def login_local(self, *, email: str, password: str) -> LocalLoginSuccess:
        user = self._find_user_by_email(email)
        if user is None:
            raise LoginError("Invalid email or password.")

        self._ensure_login_allowed(user)

        if not verify_password(password, user.hashed_password):
            self._register_failed_login(user)
            raise LoginError("Invalid email or password.")

        self._register_successful_login(user)
        password_change_required = bool(user.must_change_password)

        has_mfa_enabled = self.has_mfa_enabled(user_id=user.id)
        if has_mfa_enabled:
            challenge = self._create_mfa_challenge(user_id=user.id)
            raise MfaRequiredError(challenge)

        mfa_setup_recommended, mfa_setup_required = self.local_login_onboarding_flags(
            has_mfa_enabled=has_mfa_enabled
        )
        return LocalLoginSuccess(
            session_token=self.create_session(user_id=user.id, auth_method="password"),
            mfa_setup_recommended=mfa_setup_recommended,
            mfa_setup_required=mfa_setup_required,
            password_change_required=password_change_required,
        )

    def create_session(self, *, user_id: UUID, auth_method: SessionAuthMethod = "unknown") -> str:
        token = mint_opaque_token()
        expires_at = utc_now() + self.settings.session_access_ttl
        self.session.add(
            AuthSession(
                user_id=user_id,
                token_hash=hash_opaque_token(token),
                auth_method=auth_method,
                expires_at=expires_at,
                revoked_at=None,
            )
        )
        return token

    def local_login_onboarding_flags(self, *, has_mfa_enabled: bool) -> tuple[bool, bool]:
        if has_mfa_enabled:
            return False, False
        if self.get_policy().password_mfa_required:
            return False, True
        return True, False

    def totp_onboarding_flags(
        self,
        *,
        has_mfa_enabled: bool,
        auth_via: AuthVia,
        session_auth_method: str | None,
    ) -> tuple[bool, bool, bool]:
        if has_mfa_enabled:
            return False, False, False

        if auth_via is not AuthVia.SESSION or (session_auth_method or "").strip() != "password":
            return False, False, False

        if self.get_policy().password_mfa_required:
            return False, True, False
        return True, False, True

    def revoke_session(self, *, session_id: UUID) -> None:
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id)
            .where(AuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )

    def revoke_all_sessions_for_user(self, *, user_id: UUID) -> None:
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id)
            .where(AuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    def is_password_reset_enabled(self) -> bool:
        policy = self.get_policy()
        return bool(policy.password_reset_enabled and policy.mode != "idp_only")

    def forgot_password(self, *, email: str) -> None:
        self._ensure_password_reset_enabled()
        user = self._find_user_by_email(email)
        if user is None or not user.is_active:
            return

        raw = mint_opaque_token(32)
        expires_at = utc_now() + PASSWORD_RESET_TTL
        self.session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_opaque_token(raw),
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        assert self.delivery is not None
        self.delivery.send_reset(email=user.email, token=raw, expires_at=expires_at)

    def reset_password(self, *, token: str, new_password: str) -> None:
        self._ensure_password_reset_enabled()
        self._enforce_password_policy(new_password, field_path="newPassword")
        token_hash = hash_opaque_token(token)
        now = utc_now()
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .where(PasswordResetToken.consumed_at.is_(None))
            .where(PasswordResetToken.expires_at > now)
            .limit(1)
        )
        reset = self.session.execute(stmt).scalar_one_or_none()
        if reset is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired.",
            )

        user = self.session.get(User, reset.user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired.",
            )

        user.hashed_password = hash_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        user.must_change_password = False
        reset.consumed_at = now
        self.revoke_all_sessions_for_user(user_id=user.id)

    def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )
        self._enforce_password_policy(new_password, field_path="newPassword")
        user.hashed_password = hash_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        user.must_change_password = False

    # ------------------------------------------------------------------
    # MFA
    # ------------------------------------------------------------------

    def has_mfa_enabled(self, *, user_id: UUID) -> bool:
        mfa = self.session.get(UserMfaTotp, user_id)
        return mfa is not None and mfa.verified_at is not None

    def get_totp_status(
        self,
        *,
        user: User,
    ) -> tuple[bool, datetime | None, int | None]:
        mfa = self.session.get(UserMfaTotp, user.id)
        if mfa is None or mfa.verified_at is None:
            return False, None, None
        return True, mfa.enrolled_at, len(mfa.recovery_code_hashes)

    def start_totp_enrollment(self, *, user: User) -> tuple[str, str, str]:
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret, self.settings)
        mfa = self.session.get(UserMfaTotp, user.id)
        if mfa is None:
            mfa = UserMfaTotp(
                user_id=user.id,
                secret_enc=encrypted,
                enrolled_at=None,
                verified_at=None,
                recovery_code_hashes=[],
            )
            self.session.add(mfa)
        else:
            mfa.secret_enc = encrypted
            mfa.enrolled_at = None
            mfa.verified_at = None
            mfa.recovery_code_hashes = []

        issuer = "ADE"
        account_name = user.email
        label = quote(f"{issuer}:{account_name}")
        issuer_q = quote(issuer)
        uri = (
            f"otpauth://totp/{label}?secret={secret}"
            f"&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"
        )
        return uri, issuer, account_name

    def confirm_totp_enrollment(self, *, user: User, code: str) -> list[str]:
        mfa = self.session.get(UserMfaTotp, user.id)
        if mfa is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MFA enrollment was not started.")
        secret = decrypt_secret(mfa.secret_enc, self.settings)
        if not verify_totp(secret, code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid one-time password.")
        now = utc_now()
        recovery = generate_recovery_codes()
        mfa.enrolled_at = now
        mfa.verified_at = now
        mfa.recovery_code_hashes = hash_recovery_codes(recovery)
        return recovery

    def regenerate_recovery_codes(self, *, user: User, code: str) -> list[str]:
        mfa = self.session.get(UserMfaTotp, user.id)
        if mfa is None or mfa.verified_at is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MFA is not enabled.")

        secret = decrypt_secret(mfa.secret_enc, self.settings)
        valid = verify_totp(secret, code)
        if not valid:
            normalized_recovery_code = normalize_recovery_code(code)
            valid = verify_recovery_code(normalized_recovery_code, mfa.recovery_code_hashes)
        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid one-time password.")

        recovery = generate_recovery_codes()
        mfa.recovery_code_hashes = hash_recovery_codes(recovery)
        return recovery

    def disable_totp(self, *, user: User) -> None:
        policy = self.get_policy()
        if policy.mode == "idp_only" and self._is_global_admin(user):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Global-admin users must keep MFA enabled while "
                    "identity provider-only sign-in is enabled."
                ),
            )
        self.session.execute(delete(UserMfaTotp).where(UserMfaTotp.user_id == user.id))

    def verify_challenge(self, *, challenge_token: str, code: str) -> LocalLoginSuccess:
        token_hash = hash_opaque_token(challenge_token)
        now = utc_now()
        stmt = (
            select(MfaChallenge)
            .where(MfaChallenge.challenge_hash == token_hash)
            .where(MfaChallenge.consumed_at.is_(None))
            .where(MfaChallenge.expires_at > now)
            .limit(1)
        )
        challenge = self.session.execute(stmt).scalar_one_or_none()
        if challenge is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="MFA challenge is invalid or expired.",
            )

        user = self.session.get(User, challenge.user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="MFA challenge is invalid or expired.",
            )
        mfa = self.session.get(UserMfaTotp, user.id)
        if mfa is None or mfa.verified_at is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="MFA challenge is invalid or expired.",
            )

        valid = False
        secret = decrypt_secret(mfa.secret_enc, self.settings)
        if verify_totp(secret, code):
            valid = True
        else:
            normalized_recovery_code = normalize_recovery_code(code)
            if verify_recovery_code(normalized_recovery_code, mfa.recovery_code_hashes):
                # Single-use recovery code.
                used_hashes = set(hash_recovery_codes([normalized_recovery_code]))
                mfa.recovery_code_hashes = [
                    value for value in mfa.recovery_code_hashes if value not in used_hashes
                ]
                valid = True

        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid one-time password.")

        challenge.consumed_at = now
        self._register_successful_login(user)
        return LocalLoginSuccess(
            session_token=self.create_session(user_id=user.id, auth_method="password"),
            mfa_setup_recommended=False,
            mfa_setup_required=False,
            password_change_required=bool(user.must_change_password),
        )

    def _create_mfa_challenge(self, *, user_id: UUID) -> str:
        raw = mint_opaque_token()
        self.session.add(
            MfaChallenge(
                user_id=user_id,
                challenge_hash=hash_opaque_token(raw),
                expires_at=utc_now() + MFA_CHALLENGE_TTL,
                consumed_at=None,
            )
        )
        return raw

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_login_allowed(self, user: User) -> None:
        if not user.is_active:
            raise LoginError("Invalid email or password.")

        if user.locked_until and user.locked_until > utc_now():
            raise HTTPException(
                status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to failed login attempts.",
            )

        policy = self.get_policy()
        if policy.mode != "idp_only":
            return

        if not self._is_global_admin(user):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "sso_enforced",
                    "message": "Single sign-on is enforced for this account.",
                },
            )

        if not self.has_mfa_enabled(user_id=user.id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "admin_mfa_required",
                    "message": (
                        "Global-admin users must enroll MFA for local login while SSO is enforced."
                    ),
                },
            )

    def _ensure_password_reset_enabled(self) -> None:
        if self.is_password_reset_enabled():
            return
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Password reset is unavailable.",
        )

    def _find_user_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        if not normalized:
            return None
        stmt = select(User).where(User.email_normalized == normalized).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def _register_failed_login(self, user: User) -> None:
        user.failed_login_count += 1
        policy = self.get_policy()
        threshold = int(policy.password_lockout_max_attempts)
        if user.failed_login_count >= threshold:
            lockout_seconds = int(policy.password_lockout_duration_seconds)
            user.locked_until = utc_now() + timedelta(seconds=lockout_seconds)

    def _register_successful_login(self, user: User) -> None:
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = utc_now()

    def _is_global_admin(self, user: User) -> bool:
        role_slugs = RbacService(session=self.session).get_global_role_slugs_for_user(user=user)
        return "global-admin" in role_slugs

    def _enforce_password_policy(self, password: str, *, field_path: str) -> None:
        policy = self.get_policy()
        complexity = PasswordComplexityPolicy(
            min_length=policy.password_min_length,
            require_uppercase=policy.password_require_uppercase,
            require_lowercase=policy.password_require_lowercase,
            require_number=policy.password_require_number,
            require_symbol=policy.password_require_symbol,
        )
        enforce_password_complexity(
            password,
            policy=complexity,
            field_path=field_path,
        )
