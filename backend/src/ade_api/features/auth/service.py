"""Authentication helpers for setup and provider discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ade_api.features.authn.service import AuthnService
from ade_api.features.rbac import RbacService
from ade_db.models import SsoProviderStatus, User
from ade_api.settings import Settings

from .schemas import (
    AuthProvider,
    AuthProviderListResponse,
    AuthSetupRequest,
    AuthSetupStatusResponse,
)


class SetupAlreadyCompletedError(RuntimeError):
    """Raised when interactive setup is invoked after users already exist."""


@dataclass(slots=True)
class AuthService:
    """Authentication helpers for setup + provider metadata."""

    session: Session
    settings: Settings

    def get_setup_status(self) -> AuthSetupStatusResponse:
        setup_required = self.is_setup_required()
        registration_mode = self._registration_mode(setup_required)
        providers = self.list_auth_providers().providers
        sso_configured = self._sso_configured()
        return AuthSetupStatusResponse(
            setup_required=setup_required,
            registration_mode=registration_mode,
            oidc_configured=sso_configured,
            providers=providers,
        )

    def is_setup_required(self) -> bool:
        result = self.session.execute(select(func.count(User.id)))
        count = int(result.scalar_one() or 0)
        return count == 0

    def list_auth_providers(self) -> AuthProviderListResponse:
        providers: list[AuthProvider] = []
        authn = AuthnService(session=self.session, settings=self.settings)
        policy = authn.get_policy()

        providers.append(
            AuthProvider(
                id="password",
                label="Email & password",
                type="password",
                start_url="/api/v1/auth/login",
            )
        )

        from ade_api.features.sso.service import SsoService

        sso_service = SsoService(session=self.session, settings=self.settings)
        active = sso_service.list_active_providers() if policy.external_enabled else []
        for provider in active[:1]:
            providers.append(
                AuthProvider(
                    id=provider.id,
                    label=provider.label,
                    type="oidc",
                    start_url="/api/v1/auth/sso/authorize",
                )
            )

        return AuthProviderListResponse(
            providers=providers,
            force_sso=bool(policy.enforce_sso),
            password_reset_enabled=authn.is_password_reset_enabled(),
        )

    def _sso_configured(self) -> bool:
        from ade_api.features.sso.service import SsoService

        sso_service = SsoService(session=self.session, settings=self.settings)
        for provider in sso_service.list_providers():
            if provider.status != SsoProviderStatus.DELETED:
                return True
        return False

    def create_first_admin(self, payload: AuthSetupRequest, *, password_hash: str) -> User:
        if not self.is_setup_required():
            raise SetupAlreadyCompletedError("Initial setup has already been completed.")

        email = str(payload.email).strip()
        display_name = (payload.display_name or "").strip() or None
        now = datetime.now(tz=UTC)

        user = User(
            email=email,
            hashed_password=password_hash,
            display_name=display_name,
            is_active=True,
            is_verified=True,
            is_service_account=False,
            last_login_at=now,
            failed_login_count=0,
            locked_until=None,
        )
        self.session.add(user)
        self.session.flush()

        rbac = RbacService(session=self.session)
        rbac.sync_registry()
        admin_role = rbac.get_role_by_slug(slug="global-admin")
        if admin_role is not None:
            rbac.assign_role_if_missing(
                user_id=user.id,
                role_id=admin_role.id,
                workspace_id=None,
            )

        self.session.flush()
        return user

    def _registration_mode(self, setup_required: bool) -> str:
        if setup_required:
            return "setup-only"
        return "closed"


__all__ = ["AuthService", "SetupAlreadyCompletedError"]
