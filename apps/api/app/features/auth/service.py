from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from fastapi import HTTPException, Request, Response, status
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.features.roles.service import (
    assign_global_role,
    ensure_user_principal,
    get_global_role_by_slug,
    has_users_with_global_role,
    sync_permission_registry,
)
from apps.api.app.settings import Settings
from apps.api.app.shared.pagination import Page, paginate_sql

from ..system_settings.repository import SystemSettingsRepository
from ..users.models import User
from ..users.repository import UsersRepository
from ..users.service import UsersService
from .models import APIKey
from .repository import APIKeysRepository
from .security import (
    TokenPayload,
    create_signed_token,
    decode_signed_token,
    generate_api_key_components,
    hash_api_key,
    hash_csrf_token,
    verify_password,
)
from .utils import normalise_api_key_label, normalise_email

if TYPE_CHECKING:
    from apps.api.app.features.roles.models import Principal


@dataclass(slots=True)
class APIKeyIssueResult:
    """Result returned when issuing an API key."""

    raw_key: str
    api_key: APIKey
    user: User

    @property
    def principal_type(self) -> str:
        return "service_account" if self.user.is_service_account else "user"

    @property
    def principal_label(self) -> str:
        return self.user.label


@dataclass(slots=True)
class AuthenticatedIdentity:
    """Identity resolved during authentication."""

    user: User
    principal: Principal
    credentials: Literal["session_cookie", "bearer_token", "api_key", "development"]
    api_key: APIKey | None = None

    @property
    def label(self) -> str:
        return self.user.label


@dataclass(slots=True)
class SessionTokens:
    """Bundle of cookies issued when establishing a session."""

    session_id: str
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    access_max_age: int
    refresh_max_age: int

@dataclass(slots=True)
class OIDCProviderMetadata:
    """Discovery metadata for an OpenID Connect provider."""

    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


@dataclass(slots=True)
class SSOLoginChallenge:
    """Payload returned when initiating the SSO login flow."""

    redirect_url: str
    state_token: str
    expires_in: int
    return_to: str | None = None


@dataclass(slots=True)
class SSOState:
    """Decoded representation of the SSO state token."""

    state: str
    code_verifier: str
    nonce: str
    return_to: str | None = None


@dataclass(slots=True)
class SSOCompletionResult:
    """Outcome of a completed SSO callback."""

    user: User
    return_to: str | None


@dataclass(slots=True)
class AuthProviderOption:
    """Discovery metadata describing an interactive login option."""

    id: str
    label: str
    start_url: str
    icon_url: str | None = None


@dataclass(slots=True)
class AuthProviderDiscovery:
    """Bundle returned to the frontend when listing auth providers."""

    providers: list[AuthProviderOption]
    force_sso: bool


_DEFAULT_SSO_PROVIDER_ID = "sso"
_DEFAULT_SSO_PROVIDER_LABEL = "Single sign-on"
_DEFAULT_SSO_PROVIDER_START_URL = "/api/v1/auth/sso/login"


_SSO_STATE_TTL_SECONDS = 300
SSO_STATE_COOKIE = "backend_app_sso_state"
_MAX_PROVIDER_RESPONSE_BYTES = 64 * 1024
_HTTP_TIMEOUT = httpx.Timeout(5.0, connect=5.0, read=5.0)
_HTTP_LIMITS = httpx.Limits(max_connections=5, max_keepalive_connections=5)
_ALLOWED_JWT_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256"}
_JWT_LEEWAY_SECONDS = 60


def _is_private_host(host: str) -> bool:
    """Return ``True`` when ``host`` clearly points at a private network."""

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        lowered = host.lower()
        return lowered in {"localhost", "127.0.0.1"} or lowered.endswith(".localhost")
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _ensure_public_https_url(raw_url: str, *, purpose: str) -> httpx.URL:
    """Validate that ``raw_url`` is an HTTPS URL pointing at a public host."""

    try:
        url = httpx.URL(raw_url)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identity provider URL for {purpose}",
        ) from exc

    if url.scheme != "https":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Identity provider {purpose} must use HTTPS",
        )
    if not url.host or _is_private_host(url.host):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Identity provider {purpose} URL targets a private host",
        )
    return url
_INITIAL_SETUP_SETTING_KEY = "initial_setup"
_GLOBAL_ADMIN_ROLE_SLUG = "global-administrator"
_GLOBAL_USER_ROLE_SLUG = "global-user"


class AuthService:
    """Encapsulate login, token verification, and SSO logic."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UsersRepository(session)
        self._api_keys = APIKeysRepository(session)
        self._system_settings = SystemSettingsRepository(session)
        self._logger = logging.getLogger(__name__)

    @property
    def settings(self) -> Settings:
        return self._settings

    async def ensure_dev_identity(self) -> AuthenticatedIdentity:
        """Ensure a development identity exists when auth is bypassed."""

        email_source = self.settings.auth_disabled_user_email or "developer@example.test"
        email = normalise_email(email_source)
        display_name = (self.settings.auth_disabled_user_name or "Development User").strip() or None

        user = await self._users.get_by_email(email)
        if user is None:
            user = await self._users.create(
                email=email,
                password_hash=None,
                display_name=display_name,
                is_active=True,
                is_service_account=False,
            )
        else:
            updated = False
            if not user.is_active:
                user.is_active = True
                updated = True
            if display_name and user.display_name != display_name:
                user.display_name = display_name
                updated = True
            if updated:
                await self._session.flush()

        await sync_permission_registry(session=self._session)
        await self._assign_global_role(
            user=user,
            slug=_GLOBAL_ADMIN_ROLE_SLUG,
            session=self._session,
        )
        principal = await ensure_user_principal(session=self._session, user=user)
        return AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="development",
        )

    # ------------------------------------------------------------------
    # Password-based authentication

    async def get_initial_setup_status(self) -> tuple[bool, datetime | None]:
        """Return whether setup is required plus the completion timestamp."""

        setting = await self._system_settings.get(_INITIAL_SETUP_SETTING_KEY)
        completed_at: datetime | None = None
        if setting is not None:
            raw_completed = (setting.value or {}).get("completed_at")
            if raw_completed:
                try:
                    completed_at = datetime.fromisoformat(str(raw_completed))
                except ValueError:
                    completed_at = None
        if completed_at is not None:
            return False, completed_at

        has_admin = await has_users_with_global_role(
            session=self._session, slug=_GLOBAL_ADMIN_ROLE_SLUG
        )
        requires_setup = not has_admin
        return requires_setup, completed_at

    async def complete_initial_setup(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> User:
        """Create the first administrator and mark setup as complete."""

        session = self._session

        # Ensure the canonical permission and role registry exists before
        # provisioning the first administrator. In environments where the
        # service is executed outside of the FastAPI lifespan (for example,
        # CLI utilities or ephemeral setup scripts), the registry may not have
        # been synced yet which would previously raise a 500 when assigning the
        # `global-administrator` role. Running the synchronisation here keeps the
        # initial setup flow resilient regardless of the caller.
        await sync_permission_registry(session=session)

        async with session.begin():
            setting = await self._system_settings.get_for_update(
                _INITIAL_SETUP_SETTING_KEY
            )
            if setting is None:
                setting = await self._system_settings.create(
                    key=_INITIAL_SETUP_SETTING_KEY,
                    value={"completed_at": None},
                )

            raw_value = setting.value or {}
            completed_at = raw_value.get("completed_at")
            if completed_at:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Initial setup already completed",
                )
            has_admin = await has_users_with_global_role(
                session=session, slug=_GLOBAL_ADMIN_ROLE_SLUG
            )
            if has_admin:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Initial setup already completed",
                )

            users_service = UsersService(session=self._session)
            user = await users_service.create_admin(
                email=email,
                password=password,
                display_name=display_name,
            )

            await self._assign_global_role(
                user=user, slug=_GLOBAL_ADMIN_ROLE_SLUG, session=session
            )

            setting_value = dict(raw_value)
            setting_value["completed_at"] = datetime.now(UTC).isoformat(
                timespec="seconds"
            )
            setting.value = setting_value
            await session.flush()

            return user

    async def authenticate(self, *, email: str, password: str) -> User:
        """Return the active user matching ``email``/``password``."""

        canonical = normalise_email(email)
        user = await self._users.get_by_email(canonical)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        now = self._now()
        lockout_error = self._lockout_error(user, reference=now)
        if lockout_error is not None:
            raise lockout_error

        credential = user.credential
        if credential is None or not verify_password(password, credential.password_hash):
            await self._record_failed_login(user)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user.last_login_at = now
        user.failed_login_count = 0
        user.locked_until = None
        await self._session.flush()
        return user

    def is_secure_request(self, request: Request) -> bool:
        """Return ``True`` when the request originated over HTTPS."""

        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            for candidate in forwarded_proto.split(","):
                if candidate.strip().lower() == "https":
                    return True

        if request.scope.get("scheme"):
            return str(request.scope["scheme"]).lower() == "https"

        return request.url.scheme == "https"

    def _issue_session_tokens(
        self, *, user: User, session_id: str | None = None
    ) -> SessionTokens:
        """Create access/refresh/CSRF tokens for ``user``."""

        settings = self.settings
        session_identifier = session_id or secrets.token_urlsafe(16)
        access_delta = settings.jwt_access_ttl
        refresh_delta = settings.jwt_refresh_ttl
        csrf_token = secrets.token_urlsafe(32)
        csrf_hash = hash_csrf_token(csrf_token)

        now = datetime.now(UTC)
        access_expires_at = now + access_delta
        refresh_expires_at = now + refresh_delta

        access_token = create_signed_token(
            user_id=cast(str, user.id),
            email=user.email,
            session_id=session_identifier,
            token_type="access",
            secret=settings.jwt_secret_value,
            algorithm=settings.jwt_algorithm,
            expires_delta=access_delta,
            csrf_hash=csrf_hash,
        )
        refresh_token = create_signed_token(
            user_id=cast(str, user.id),
            email=user.email,
            session_id=session_identifier,
            token_type="refresh",
            secret=settings.jwt_secret_value,
            algorithm=settings.jwt_algorithm,
            expires_delta=refresh_delta,
            csrf_hash=csrf_hash,
        )

        return SessionTokens(
            session_id=session_identifier,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
            access_max_age=int(access_delta.total_seconds()),
            refresh_max_age=int(refresh_delta.total_seconds()),
        )

    async def _assign_global_role(
        self,
        *,
        user: User,
        slug: str,
        session: AsyncSession | None = None,
    ) -> None:
        target_session = session or self._session
        role = await get_global_role_by_slug(session=target_session, slug=slug)
        if role is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Global role '{slug}' is not configured",
            )
        await assign_global_role(
            session=target_session,
            user_id=cast(str, user.id),
            role_id=cast(str, role.id),
        )

    async def start_session(self, *, user: User) -> SessionTokens:
        """Return freshly minted session cookies for ``user``."""

        return self._issue_session_tokens(user=user)

    async def refresh_session(
        self, *, payload: TokenPayload, user: User
    ) -> SessionTokens:
        """Rotate the session using the existing ``payload``."""

        if payload.token_type != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
        return self._issue_session_tokens(user=user, session_id=payload.session_id)

    def decode_token(
        self, token: str, *, expected_type: Literal["access", "refresh", "any"] = "any"
    ) -> TokenPayload:
        """Decode ``token`` and ensure the expected token type."""

        payload = decode_signed_token(
            token=token,
            secret=self.settings.jwt_secret_value,
            algorithms=[self.settings.jwt_algorithm],
        )
        if expected_type != "any" and payload.token_type != expected_type:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unexpected token type")
        return payload

    def apply_session_cookies(
        self, response: Response, tokens: SessionTokens, *, secure: bool
    ) -> None:
        """Attach cookies for ``tokens`` to ``response``."""

        settings = self.settings
        session_path = self._normalise_cookie_path(settings.session_cookie_path)
        refresh_path = self._refresh_cookie_path(session_path)
        response.set_cookie(
            key=settings.session_cookie_name,
            value=tokens.access_token,
            max_age=tokens.access_max_age,
            domain=settings.session_cookie_domain,
            path=session_path,
            secure=secure,
            httponly=True,
            samesite="lax",
        )
        response.set_cookie(
            key=settings.session_refresh_cookie_name,
            value=tokens.refresh_token,
            max_age=tokens.refresh_max_age,
            domain=settings.session_cookie_domain,
            path=refresh_path,
            secure=secure,
            httponly=True,
            samesite="lax",
        )
        response.set_cookie(
            key=settings.session_csrf_cookie_name,
            value=tokens.csrf_token,
            max_age=tokens.access_max_age,
            domain=settings.session_cookie_domain,
            path=session_path,
            secure=secure,
            httponly=False,
            samesite="lax",
        )
        response.headers["X-CSRF-Token"] = tokens.csrf_token

    def clear_session_cookies(self, response: Response) -> None:
        """Remove session cookies from the client response."""

        settings = self.settings
        session_path = self._normalise_cookie_path(settings.session_cookie_path)
        refresh_path = self._refresh_cookie_path(session_path)
        response.delete_cookie(
            key=settings.session_cookie_name,
            domain=settings.session_cookie_domain,
            path=session_path,
        )
        response.delete_cookie(
            key=settings.session_refresh_cookie_name,
            domain=settings.session_cookie_domain,
            path=refresh_path,
        )
        response.delete_cookie(
            key=settings.session_csrf_cookie_name,
            domain=settings.session_cookie_domain,
            path=session_path,
        )

    def enforce_csrf(self, request: Request, payload: TokenPayload) -> None:
        """Verify the CSRF token for mutating requests."""

        safe_methods = {"GET", "HEAD", "OPTIONS"}
        if request.method.upper() in safe_methods:
            return

        csrf_cookie = request.cookies.get(self.settings.session_csrf_cookie_name)
        header_token = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not header_token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
        if csrf_cookie != header_token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

        expected_hash = payload.csrf_hash
        if not expected_hash:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")
        if hash_csrf_token(header_token) != expected_hash:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

    def _normalise_cookie_path(self, raw_path: str | None) -> str:
        path = (raw_path or "/").strip()
        if not path:
            return "/"
        if not path.startswith("/"):
            path = f"/{path}"
        return path

    def _refresh_cookie_path(self, session_path: str) -> str:
        base = session_path.rstrip("/")
        suffix = "/auth/session/refresh"
        if not base or base == "/":
            return "/api/v1" + suffix
        return f"{base}{suffix}"

    def extract_session_payloads(
        self, request: Request, *, include_refresh: bool = True
    ) -> tuple[TokenPayload, TokenPayload | None]:
        """Decode the access token and optional refresh token from the request."""

        raw_session_cookie = request.cookies.get(self.settings.session_cookie_name)
        session_cookie = (raw_session_cookie or "").strip()
        if not session_cookie:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session token missing")
        try:
            access_payload = self.decode_token(session_cookie, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token",
            ) from exc

        raw_refresh_cookie = request.cookies.get(self.settings.session_refresh_cookie_name)
        refresh_cookie = (raw_refresh_cookie or "").strip()
        if not refresh_cookie:
            if include_refresh:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
            return access_payload, None
        try:
            refresh_payload = self.decode_token(refresh_cookie, expected_type="refresh")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from exc

        if refresh_payload.session_id != access_payload.session_id or (
            refresh_payload.user_id != access_payload.user_id
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session mismatch")

        return access_payload, refresh_payload

    def get_provider_discovery(self) -> AuthProviderDiscovery:
        """Return configured providers and the force-SSO flag."""

        providers: list[AuthProviderOption] = []
        if self.settings.oidc_enabled:
            providers.append(
                AuthProviderOption(
                    id=_DEFAULT_SSO_PROVIDER_ID,
                    label=_DEFAULT_SSO_PROVIDER_LABEL,
                    start_url=_DEFAULT_SSO_PROVIDER_START_URL,
                    icon_url=None,
                )
            )
        return AuthProviderDiscovery(
            providers=providers, force_sso=self.settings.auth_force_sso
        )

    async def resolve_user(self, payload: TokenPayload) -> User:
        """Return the user represented by ``payload`` if active."""

        user = await self._users.get_by_id(payload.user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        lockout_error = self._lockout_error(user)
        if lockout_error is not None:
            raise lockout_error
        return user

    # ------------------------------------------------------------------
    # API key lifecycle

    async def issue_api_key_for_email(
        self,
        *,
        email: str,
        expires_in_days: int | None = None,
        label: str | None = None,
    ) -> APIKeyIssueResult:
        """Issue an API key for the user identified by ``email``."""

        canonical = normalise_email(email)
        user = await self._users.get_by_email(canonical)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
        if not user.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Target user is inactive")

        expires_at = None
        if expires_in_days is not None:
            expires_at = self._now() + timedelta(days=expires_in_days)

        return await self.issue_api_key(
            user=user, expires_at=expires_at, label=label
        )

    async def issue_api_key(
        self,
        *,
        user: User,
        expires_at: datetime | None = None,
        label: str | None = None,
    ) -> APIKeyIssueResult:
        """Persist an API key for ``user`` and return the raw secret."""

        prefix, secret = generate_api_key_components()
        token_hash = hash_api_key(secret)
        cleaned_label = normalise_api_key_label(label)
        record = await self._api_keys.create(
            user_id=cast(str, user.id),
            token_prefix=prefix,
            token_hash=token_hash,
            expires_at=expires_at,
            label=cleaned_label,
        )
        return APIKeyIssueResult(
            raw_key=f"{prefix}.{secret}",
            api_key=record,
            user=user,
        )

    async def issue_api_key_for_user_id(
        self,
        *,
        user_id: str,
        expires_in_days: int | None = None,
        label: str | None = None,
    ) -> APIKeyIssueResult:
        """Issue an API key for the active user identified by ``user_id``."""

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
        if not user.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Target user is inactive")

        expires_at = None
        if expires_in_days is not None:
            expires_at = self._now() + timedelta(days=expires_in_days)

        return await self.issue_api_key(
            user=user, expires_at=expires_at, label=label
        )

    async def list_api_keys(self, *, include_revoked: bool = False) -> list[APIKey]:
        """Return all issued API keys ordered by creation time."""

        return await self._api_keys.list_api_keys(include_revoked=include_revoked)

    async def paginate_api_keys(
        self,
        *,
        include_revoked: bool,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[APIKey]:
        """Return paginated API keys."""

        stmt = self._api_keys.query_api_keys(include_revoked=include_revoked)
        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=(APIKey.created_at.desc(),),
        )

    async def revoke_api_key(self, api_key_id: str) -> None:
        """Remove the API key identified by ``api_key_id``."""

        record = await self._api_keys.get_by_id(api_key_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
        if record.revoked_at is not None:
            return
        await self._api_keys.revoke(record, revoked_at=self._now())

    async def authenticate_api_key(
        self, raw_key: str, *, request: Request | None = None
    ) -> AuthenticatedIdentity:
        """Return the identity associated with ``raw_key`` if valid."""

        try:
            prefix, secret = raw_key.split(".", 1)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            ) from exc

        record = await self._api_keys.get_by_prefix(prefix)
        if record is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        now = self._now()
        expires_at = self._ensure_aware(record.expires_at)
        if expires_at and expires_at < now:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="API key expired")
        revoked_at = self._ensure_aware(record.revoked_at)
        if revoked_at and revoked_at <= now:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="API key revoked")

        expected = hash_api_key(secret)
        if not secrets.compare_digest(expected, record.token_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        user = record.user
        if user is None:
            user = await self._users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        principal = await ensure_user_principal(session=self._session, user=user)
        identity = AuthenticatedIdentity(
            user=user,
            principal=principal,
            api_key=record,
            credentials="api_key",
        )

        if request is not None:
            await self._touch_api_key(record, request=request)
        return identity

    async def _touch_api_key(self, record: APIKey, *, request: Request) -> None:
        interval = self.settings.session_last_seen_interval
        now = self._now()
        last_seen = self._ensure_aware(record.last_seen_at)
        if last_seen is not None and interval.total_seconds() > 0:
            if (now - last_seen) < interval:
                return

        record.last_seen_at = now
        client = request.client
        if client and client.host:
            record.last_seen_ip = client.host[:45]
        user_agent = request.headers.get("user-agent")
        if user_agent:
            record.last_seen_user_agent = user_agent[:255]
        await self._session.flush()

    # ------------------------------------------------------------------
    # SSO helpers

    async def prepare_sso_login(self, *, return_to: str | None = None) -> SSOLoginChallenge:
        """Return redirect metadata and a signed state token."""

        if not self.settings.oidc_enabled:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO not configured")

        metadata = await self._get_oidc_metadata()
        issued_at = self._now()
        state = secrets.token_urlsafe(16)
        code_verifier = self._build_code_verifier()
        code_challenge = self._build_code_challenge(code_verifier)
        nonce = secrets.token_urlsafe(16)
        normalised_return = self._normalise_return_target(return_to)
        state_token = self._encode_sso_state(
            state=state,
            code_verifier=code_verifier,
            nonce=nonce,
            issued_at=issued_at,
            return_to=normalised_return,
        )

        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": str(self.settings.oidc_redirect_url),
            "scope": " ".join(self.settings.oidc_scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        redirect_url = f"{metadata.authorization_endpoint}?{urlencode(params)}"
        return SSOLoginChallenge(
            redirect_url=redirect_url,
            state_token=state_token,
            expires_in=_SSO_STATE_TTL_SECONDS,
            return_to=normalised_return,
        )

    def decode_sso_state(self, token: str) -> SSOState:
        """Return the stored SSO state details."""

        secret = self.settings.jwt_secret_value
        if not secret:
            raise RuntimeError(
                "jwt_secret must be configured when authentication is enabled",
            )

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["exp", "iat", "state", "code_verifier", "nonce"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="SSO state expired") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid SSO state") from exc

        return_to_raw = payload.get("return_to")
        return_to: str | None = None
        if isinstance(return_to_raw, str) and return_to_raw:
            return_to = self._normalise_return_target(return_to_raw)

        return SSOState(
            state=str(payload["state"]),
            code_verifier=str(payload["code_verifier"]),
            nonce=str(payload["nonce"]),
            return_to=return_to,
        )

    async def complete_sso_login(
        self,
        *,
        code: str,
        state: str,
        state_token: str,
    ) -> SSOCompletionResult:
        """Complete the SSO flow and return the authenticated user."""

        stored_state = self.decode_sso_state(state_token)
        if stored_state.state != state:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="State mismatch")

        token_response = await self._exchange_authorization_code(
            code=code,
            code_verifier=stored_state.code_verifier,
        )
        metadata = await self._get_oidc_metadata()

        id_token = token_response.get("id_token")
        access_token = token_response.get("access_token")
        token_type = str(token_response.get("token_type", "")).lower()
        if not id_token or not access_token or token_type != "bearer":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Invalid token response from identity provider",
            )

        issuer_value = str(self.settings.oidc_issuer or "")

        id_claims = await self._verify_jwt_via_jwks(
            token=id_token,
            jwks_uri=metadata.jwks_uri,
            audience=self.settings.oidc_client_id,
            issuer=issuer_value,
            nonce=stored_state.nonce,
        )

        email = str(id_claims.get("email") or "")
        subject = str(id_claims.get("sub") or "")
        if not email or not subject:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider response missing required claims",
            )

        user = await self._resolve_sso_user(
            provider=issuer_value,
            subject=subject,
            email=email,
        )
        now = self._now()
        user.last_login_at = now
        user.failed_login_count = 0
        user.locked_until = None
        await self._session.flush()
        return SSOCompletionResult(user=user, return_to=stored_state.return_to)

    # ------------------------------------------------------------------
    # Internal helpers

    def _lockout_error(
        self,
        user: User,
        *,
        reference: datetime | None = None,
    ) -> HTTPException | None:
        locked_until = self._ensure_aware(user.locked_until)
        reference_time = reference or self._now()
        if locked_until is None or locked_until <= reference_time:
            return None

        if locked_until < reference_time:
            locked_until = reference_time

        failed_attempts = max(int(user.failed_login_count or 0), 0)
        retry_after_seconds = max(
            int((locked_until - reference_time).total_seconds()),
            0,
        )
        formatted_unlock = (
            locked_until.astimezone(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        message = (
            "Your account has been temporarily locked after "
            f"{failed_attempts or 'multiple'} failed sign-in attempts. "
            f"Try again after {formatted_unlock}."
        )

        detail: dict[str, object] = {
            "message": message,
            "lockedUntil": formatted_unlock,
            "failedAttempts": failed_attempts,
            "retryAfterSeconds": retry_after_seconds,
        }
        headers: dict[str, str] | None = None
        if retry_after_seconds > 0:
            headers = {"Retry-After": str(retry_after_seconds)}

        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=headers,
        )

    async def _record_failed_login(self, user: User) -> None:
        user.failed_login_count += 1
        threshold = self.settings.failed_login_lock_threshold
        if user.failed_login_count >= threshold:
            user.failed_login_count = threshold
            lock_duration = self.settings.failed_login_lock_duration
            user.locked_until = self._now() + lock_duration
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(user)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _build_code_verifier() -> str:
        return AuthService._encode_base64(secrets.token_bytes(32))

    @staticmethod
    def _build_code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return AuthService._encode_base64(digest)

    @staticmethod
    def _ensure_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _encode_base64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _normalise_return_target(self, value: str | None) -> str | None:
        """Validate and canonicalise the requested post-login redirect."""

        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.startswith("//"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Invalid return target",
            )
        if candidate.startswith("/"):
            return candidate

        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            expected = urlparse(self.settings.server_public_url)
            if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Invalid return target",
                )
            path = parsed.path or "/"
            query = f"?{parsed.query}" if parsed.query else ""
            fragment = f"#{parsed.fragment}" if parsed.fragment else ""
            return f"{path}{query}{fragment}"

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid return target",
        )

    def _encode_sso_state(
        self,
        *,
        state: str,
        code_verifier: str,
        nonce: str,
        issued_at: datetime,
        return_to: str | None,
    ) -> str:
        secret = self.settings.jwt_secret_value
        if not secret:
            raise RuntimeError(
                "jwt_secret must be configured when authentication is enabled",
            )

        payload = {
            "state": state,
            "code_verifier": code_verifier,
            "nonce": nonce,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + timedelta(seconds=_SSO_STATE_TTL_SECONDS)).timestamp()),
        }
        if return_to:
            payload["return_to"] = return_to
        return jwt.encode(payload, secret, algorithm=self.settings.jwt_algorithm)

    async def _get_oidc_metadata(self) -> OIDCProviderMetadata:
        issuer = str(self.settings.oidc_issuer or "")
        if not issuer:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC issuer is not configured",
            )

        discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
        url = _ensure_public_https_url(discovery_url, purpose="discovery")
        data = await self._fetch_provider_json(url, purpose="discovery")

        try:
            metadata = OIDCProviderMetadata(
                authorization_endpoint=str(data["authorization_endpoint"]),
                token_endpoint=str(data["token_endpoint"]),
                jwks_uri=str(data["jwks_uri"]),
            )
        except KeyError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Incomplete SSO discovery document",
            ) from exc

        return metadata

    async def _fetch_provider_json(
        self, url: httpx.URL, *, purpose: str
    ) -> Mapping[str, Any]:
        """Fetch and validate a JSON document from the identity provider."""

        try:
            async with httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=_HTTP_LIMITS,
                follow_redirects=False,
            ) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f"Unable to contact identity provider during {purpose}",
            ) from exc

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Identity provider returned an error during {purpose}",
            )

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_PROVIDER_RESPONSE_BYTES:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail=f"Identity provider response too large during {purpose}",
                    )
            except ValueError:
                pass
        if len(response.content) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Identity provider response too large during {purpose}",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Identity provider returned invalid JSON during {purpose}",
            ) from exc

        if not isinstance(data, Mapping):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Identity provider returned invalid JSON during {purpose}",
            )

        return data

    async def _exchange_authorization_code(
        self,
        *,
        code: str,
        code_verifier: str,
    ) -> Mapping[str, Any]:
        metadata = await self._get_oidc_metadata()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": str(self.settings.oidc_redirect_url),
            "code_verifier": code_verifier,
            "client_id": self.settings.oidc_client_id,
        }

        client_secret = self.settings.oidc_client_secret
        if client_secret is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC client secret is not configured",
            )
        secret_value = client_secret.get_secret_value()
        payload["client_secret"] = secret_value
        auth: tuple[str, str] = (self.settings.oidc_client_id or "", secret_value)

        token_endpoint = _ensure_public_https_url(
            metadata.token_endpoint,
            purpose="token exchange",
        )

        try:
            async with httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=_HTTP_LIMITS,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    token_endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    auth=cast(tuple[str | bytes, str | bytes], auth),
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="Unable to contact identity provider",
            ) from exc

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="SSO token exchange failed",
            )

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_PROVIDER_RESPONSE_BYTES:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail="Identity provider response too large",
                    )
            except ValueError:
                pass
        if len(response.content) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider response too large",
            )

        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider returned invalid JSON",
            ) from exc

    async def _verify_jwt_via_jwks(
        self,
        *,
        token: str,
        jwks_uri: str,
        audience: str | None,
        issuer: str,
        nonce: str | None = None,
    ) -> Mapping[str, Any]:
        if not issuer:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC issuer is not configured",
            )

        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Invalid token from identity provider",
            ) from exc

        algorithm = str(header.get("alg") or "")
        if algorithm not in _ALLOWED_JWT_ALGORITHMS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider token used an unsupported algorithm",
            )

        kid = header.get("kid")
        keys = await self._get_jwks_keys(jwks_uri)
        jwk = self._select_jwk(keys, kid, algorithm)
        if jwk is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No signing key matched the identity provider response",
            )

        signing_key = self._materialise_jwk(jwk, algorithm)
        options: dict[str, Any] = {"require": ["exp", "iat", "iss", "sub"]}
        if audience is not None:
            options["require"].append("aud")
        else:
            options["verify_aud"] = False

        decode_kwargs: dict[str, Any] = {
            "key": signing_key,
            "algorithms": [algorithm],
            "issuer": issuer,
            "leeway": _JWT_LEEWAY_SECONDS,
            "options": options,
        }
        if audience is not None:
            decode_kwargs["audience"] = audience

        try:
            payload = jwt.decode(token, **decode_kwargs)
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Invalid token from identity provider",
            ) from exc

        if nonce is not None and payload.get("nonce") != nonce:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Invalid SSO nonce",
            )

        return payload

    async def _get_jwks_keys(self, jwks_uri: str) -> list[dict[str, Any]]:
        if not jwks_uri:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Identity provider JWKS endpoint is not configured",
            )

        url = _ensure_public_https_url(jwks_uri, purpose="JWKS retrieval")
        document = await self._fetch_provider_json(url, purpose="JWKS retrieval")
        keys = document.get("keys")
        if not isinstance(keys, list) or not keys:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider JWKS document is missing keys",
            )

        parsed: list[dict[str, Any]] = []
        for item in keys:
            if isinstance(item, Mapping):
                parsed.append({str(k): v for k, v in item.items()})

        if not parsed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider JWKS document is missing keys",
            )

        return parsed

    @staticmethod
    def _select_jwk(
        keys: list[dict[str, Any]], kid: str | None, algorithm: str
    ) -> dict[str, Any] | None:
        if kid:
            for key in keys:
                if str(key.get("kid")) == kid:
                    return key
            return None

        if len(keys) == 1:
            return keys[0]

        for key in keys:
            key_alg = str(key.get("alg") or "")
            if key_alg == algorithm:
                return key
        for key in keys:
            if str(key.get("use")) == "sig":
                return key
        return None

    @staticmethod
    def _materialise_jwk(jwk: Mapping[str, Any], algorithm: str) -> Any:
        jwk_payload = json.dumps(dict(jwk))
        if algorithm.startswith("RS"):
            return RSAAlgorithm.from_jwk(jwk_payload)
        if algorithm.startswith("ES"):
            return ECAlgorithm.from_jwk(jwk_payload)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Identity provider token used an unsupported algorithm",
        )

    async def _resolve_sso_user(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
    ) -> User:
        canonical = normalise_email(email)
        if "@" not in canonical:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider response missing required claims",
            )

        identity = await self._users.get_identity(provider, subject)
        if identity is None:
            user = await self._users.get_by_email(canonical)
            if user is None:
                if not self.settings.auth_sso_auto_provision:
                    self._logger.warning(
                        "SSO login denied for %s: auto-provisioning disabled",
                        canonical,
                    )
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        detail="User not invited",
                    )
                user = await self._users.create(
                    email=canonical,
                    is_active=True,
                    is_service_account=False,
                )
                await self._assign_global_role(
                    user=user, slug=_GLOBAL_USER_ROLE_SLUG
                )
                self._logger.info(
                    "Provisioned new SSO user %s via %s", canonical, provider
                )
            elif not user.is_active:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled",
                )
            else:
                lockout_error = self._lockout_error(user)
                if lockout_error is not None:
                    raise lockout_error

                conflicting_identity = next(
                    (
                        record
                        for record in getattr(user, "identities", []) or []
                        if record.provider == provider and record.subject != subject
                    ),
                    None,
                )
                if conflicting_identity is not None:
                    self._logger.error(
                        "SSO identity conflict for %s: subject mismatch",
                        canonical,
                    )
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        detail="SSO identity conflict for this user; contact an administrator",
                    )
            if user.email_canonical != canonical:
                user.email = email.strip()
            identity = await self._users.create_identity(
                user=user,
                provider=provider,
                subject=subject,
            )
        else:
            user = identity.user or await self._users.get_by_id(identity.user_id)
            if user is None:
                msg = "SSO identity is orphaned"
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail=msg)
            if not user.is_active:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User account is disabled")
            lockout_error = self._lockout_error(user)
            if lockout_error is not None:
                raise lockout_error
            if user.email_canonical != canonical:
                user.email = email.strip()

        identity.last_authenticated_at = self._now()
        await self._session.flush()
        return user


__all__ = [
    "APIKeyIssueResult",
    "AuthenticatedIdentity",
    "AuthProviderDiscovery",
    "AuthProviderOption",
    "AuthService",
    "OIDCProviderMetadata",
    "SSOCompletionResult",
    "SSOLoginChallenge",
    "SSO_STATE_COOKIE",
]
