"""Authentication helpers for setup and provider discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.rbac import RbacService
from ade_api.models import User
from ade_api.settings import Settings

from .schemas import AuthProvider, AuthProviderListResponse, AuthSetupRequest, AuthSetupStatusResponse


class SetupAlreadyCompletedError(RuntimeError):
    """Raised when interactive setup is invoked after users already exist."""


@dataclass(slots=True)
class AuthService:
    """Authentication helpers for setup + provider metadata."""

    session: AsyncSession
    settings: Settings

    async def get_setup_status(self) -> AuthSetupStatusResponse:
        setup_required = await self.is_setup_required()
        registration_mode = self._registration_mode(setup_required)
        providers = self.list_auth_providers().providers
        return AuthSetupStatusResponse(
            setup_required=setup_required,
            registration_mode=registration_mode,
            oidc_configured=bool(self.settings.oidc_enabled),
            providers=providers,
        )

    async def is_setup_required(self) -> bool:
        result = await self.session.execute(select(func.count(User.id)))
        count = int(result.scalar_one() or 0)
        return count == 0

    def list_auth_providers(self) -> AuthProviderListResponse:
        providers: list[AuthProvider] = []

        if not self.settings.auth_force_sso:
            providers.append(
                AuthProvider(
                    id="password",
                    label="Email & password",
                    type="password",
                    start_url="/api/v1/auth/cookie/login",
                )
            )

        if self.settings.oidc_enabled:
            providers.append(
                AuthProvider(
                    id="oidc",
                    label="Single sign-on",
                    type="oidc",
                    start_url="/api/v1/auth/oidc/oidc/authorize",
                )
            )

        return AuthProviderListResponse(
            providers=providers,
            force_sso=bool(self.settings.auth_force_sso),
        )

    async def create_first_admin(self, payload: AuthSetupRequest, *, password_hash: str) -> User:
        if not await self.is_setup_required():
            raise SetupAlreadyCompletedError("Initial setup has already been completed.")

        email = str(payload.email).strip()
        display_name = (payload.display_name or "").strip() or None
        now = datetime.now(tz=UTC)

        user = User(
            email=email,
            hashed_password=password_hash,
            display_name=display_name,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            is_service_account=False,
            last_login_at=now,
            failed_login_count=0,
            locked_until=None,
        )
        self.session.add(user)
        await self.session.flush()

        rbac = RbacService(session=self.session)
        await rbac.sync_registry()
        admin_role = await rbac.get_role_by_slug(slug="global-admin")
        if admin_role is not None:
            await rbac.assign_role_if_missing(
                user_id=user.id,
                role_id=admin_role.id,
                workspace_id=None,
            )

        await self.session.flush()
        return user

    def _registration_mode(self, setup_required: bool) -> str:
        if setup_required:
            return "setup-only"
        if self.settings.allow_public_registration:
            return "open"
        return "closed"


__all__ = ["AuthService", "SetupAlreadyCompletedError"]
