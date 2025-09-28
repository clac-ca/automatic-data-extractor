from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request, Response, status
from jwt import PyJWKClient

from ...core.service import BaseService, ServiceContext
from ..users.models import User, UserRole
from ..users.repository import UsersRepository
from .models import APIKey
from .repository import APIKeysRepository
from .security import (
    TokenPayload,
    create_signed_token,
    decode_signed_token,
    generate_api_key_components,
    hash_api_key,
    hash_csrf_token,
    hash_password,
    verify_password,
)


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
    credentials: Literal["session_cookie", "bearer_token", "api_key"]
    api_key: APIKey | None = None

    @property
    def label(self) -> str:
        return self.user.label

    @property
    def is_service_account(self) -> bool:
        return bool(self.user.is_service_account)


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


@dataclass(slots=True)
class SSOState:
    """Decoded representation of the SSO state token."""

    state: str
    code_verifier: str
    nonce: str


_SSO_STATE_TTL_SECONDS = 300
SSO_STATE_COOKIE = "ade_sso_state"

_METADATA_CACHE: dict[str, OIDCProviderMetadata] = {}
_JWK_CLIENTS: dict[str, PyJWKClient] = {}


def normalise_email(value: str) -> str:
    """Return a canonical representation for email comparisons."""

    candidate = value.strip()
    if not candidate:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return candidate.lower()


class AuthService(BaseService):
    """Encapsulate login, token verification, and SSO logic."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("AuthService requires a database session")
        self._users = UsersRepository(self.session)
        self._api_keys = APIKeysRepository(self.session)

    # ------------------------------------------------------------------
    # Password-based authentication

    async def authenticate(self, *, email: str, password: str) -> User:
        """Return the active user matching ``email``/``password``."""

        canonical = normalise_email(email)
        user = await self._users.get_by_email(canonical)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if user.is_service_account:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Service accounts cannot authenticate with passwords",
            )
        if not user.password_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        return user

    def is_secure_request(self, request: Request) -> bool:
        """Return ``True`` when the request originated over HTTPS."""

        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            candidate = forwarded_proto.split(",", 1)[0].strip().lower()
            if candidate:
                return candidate == "https"
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
            user_id=user.id,
            email=user.email,
            role=user.role,
            session_id=session_identifier,
            token_type="access",
            secret=settings.jwt_secret_value,
            algorithm=settings.jwt_algorithm,
            expires_delta=access_delta,
            csrf_hash=csrf_hash,
        )
        refresh_token = create_signed_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
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
        cookie_kwargs = {
            "domain": settings.session_cookie_domain,
            "path": session_path,
            "secure": secure,
            "httponly": True,
            "samesite": "lax",
        }
        response.set_cookie(
            key=settings.session_cookie_name,
            value=tokens.access_token,
            max_age=tokens.access_max_age,
            **cookie_kwargs,
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
        suffix = "/auth/refresh"
        if not base:
            return suffix
        return f"{base}{suffix}"

    async def resolve_user(self, payload: TokenPayload) -> User:
        """Return the user represented by ``payload`` if active."""

        user = await self._users.get_by_id(payload.user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        return user

    # ------------------------------------------------------------------
    # API key lifecycle

    async def issue_api_key_for_email(
        self,
        *,
        email: str,
        expires_in_days: int | None = None,
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

        return await self.issue_api_key(user=user, expires_at=expires_at)

    async def issue_api_key(
        self,
        *,
        user: User,
        expires_at: datetime | None = None,
    ) -> APIKeyIssueResult:
        """Persist an API key for ``user`` and return the raw secret."""

        prefix, secret = generate_api_key_components()
        token_hash = hash_api_key(secret)
        record = await self._api_keys.create(
            user_id=user.id,
            token_prefix=prefix,
            token_hash=token_hash,
            expires_at=expires_at.isoformat(timespec="seconds") if expires_at else None,
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

        return await self.issue_api_key(user=user, expires_at=expires_at)

    async def list_api_keys(self) -> list[APIKey]:
        """Return all issued API keys ordered by creation time."""

        return await self._api_keys.list_api_keys()

    async def revoke_api_key(self, api_key_id: str) -> None:
        """Remove the API key identified by ``api_key_id``."""

        record = await self._api_keys.get_by_id(api_key_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
        await self._api_keys.delete(record)

    async def authenticate_api_key(self, raw_key: str) -> AuthenticatedIdentity:
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

        if record.expires_at:
            expires_at = self._parse_timestamp(record.expires_at)
            if expires_at is not None and expires_at < self._now():
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="API key expired")

        expected = hash_api_key(secret)
        if not secrets.compare_digest(expected, record.token_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        user = record.user
        if user is None:
            user = await self._users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        principal = AuthenticatedIdentity(
            user=user,
            api_key=record,
            credentials="api_key",
        )

        request = self.request
        if request is not None:
            await self._touch_api_key(record, request=request)
        return principal

    async def _touch_api_key(self, record: APIKey, *, request: Request) -> None:
        interval = self.settings.session_last_seen_interval
        now = self._now()
        last_seen = self._parse_timestamp(record.last_seen_at)
        if last_seen is not None and interval.total_seconds() > 0:
            if (now - last_seen) < interval:
                return

        record.last_seen_at = now.isoformat()
        client = request.client
        if client and client.host:
            record.last_seen_ip = client.host[:45]
        user_agent = request.headers.get("user-agent")
        if user_agent:
            record.last_seen_user_agent = user_agent[:255]
        await self.session.flush()

    # ------------------------------------------------------------------
    # SSO helpers

    async def prepare_sso_login(self) -> SSOLoginChallenge:
        """Return redirect metadata and a signed state token."""

        if not self.settings.oidc_enabled:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO not configured")

        metadata = await self._get_oidc_metadata()
        issued_at = self._now()
        state = secrets.token_urlsafe(16)
        code_verifier = self._build_code_verifier()
        code_challenge = self._build_code_challenge(code_verifier)
        nonce = secrets.token_urlsafe(16)
        state_token = self._encode_sso_state(
            state=state,
            code_verifier=code_verifier,
            nonce=nonce,
            issued_at=issued_at,
        )

        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": str(self.settings.oidc_redirect_url),
            "scope": " ".join(self.settings.oidc_scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        redirect_url = f"{metadata.authorization_endpoint}?{urlencode(params)}"
        return SSOLoginChallenge(
            redirect_url=redirect_url,
            state_token=state_token,
            expires_in=_SSO_STATE_TTL_SECONDS,
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

        return SSOState(
            state=str(payload["state"]),
            code_verifier=str(payload["code_verifier"]),
            nonce=str(payload["nonce"]),
        )

    async def complete_sso_login(
        self,
        *,
        code: str,
        state: str,
        state_token: str,
    ) -> User:
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

        issuer_value = str(self.settings.oidc_issuer) if self.settings.oidc_issuer else ""

        id_claims = self._verify_jwt_via_jwks(
            token=id_token,
            jwks_uri=metadata.jwks_uri,
            audience=self.settings.oidc_client_id,
            issuer=issuer_value,
            nonce=stored_state.nonce,
        )

        resource_audience = self.settings.oidc_resource_audience
        if resource_audience:
            self._verify_jwt_via_jwks(
                token=access_token,
                jwks_uri=metadata.jwks_uri,
                audience=resource_audience,
                issuer=issuer_value,
            )

        email = str(id_claims.get("email") or "")
        subject = str(id_claims.get("sub") or "")
        email_verified = bool(id_claims.get("email_verified"))
        if not email or not subject:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Identity provider response missing required claims",
            )

        user = await self._resolve_sso_user(
            provider=issuer_value,
            subject=subject,
            email=email,
            email_verified=email_verified,
        )
        user.last_login_at = self._now().isoformat()
        await self.session.flush()
        return user

    # ------------------------------------------------------------------
    # Internal helpers

    def _now(self) -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _build_code_verifier() -> str:
        return AuthService._encode_base64(secrets.token_bytes(32))

    @staticmethod
    def _build_code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return AuthService._encode_base64(digest)

    @staticmethod
    def _encode_base64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _encode_sso_state(
        self,
        *,
        state: str,
        code_verifier: str,
        nonce: str,
        issued_at: datetime,
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
        return jwt.encode(payload, secret, algorithm=self.settings.jwt_algorithm)

    async def _get_oidc_metadata(self) -> OIDCProviderMetadata:
        issuer = str(self.settings.oidc_issuer) if self.settings.oidc_issuer else ""
        cached = _METADATA_CACHE.get(issuer)
        if cached is not None:
            return cached

        discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(discovery_url, headers={"Accept": "application/json"})
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Failed to load SSO metadata",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="Unable to contact identity provider",
            ) from exc

        data = response.json()
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

        _METADATA_CACHE[issuer] = metadata
        return metadata

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

        auth: tuple[str, str] | None = None
        client_secret = self.settings.oidc_client_secret
        if client_secret:
            secret_value = client_secret.get_secret_value()
            auth = (self.settings.oidc_client_id or "", secret_value)
            payload["client_secret"] = secret_value

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    metadata.token_endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    auth=auth,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="SSO token exchange failed",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="Unable to contact identity provider",
            ) from exc

        return response.json()

    def _verify_jwt_via_jwks(
        self,
        *,
        token: str,
        jwks_uri: str,
        audience: str | None,
        issuer: str,
        nonce: str | None = None,
    ) -> Mapping[str, Any]:
        client = self._get_jwk_client(jwks_uri)
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            options: dict[str, Any] = {"require": ["exp", "iat", "iss", "sub"]}
            if audience is not None:
                options["require"].append("aud")
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=audience,
                issuer=issuer,
                options=options,
            )
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

    def _get_jwk_client(self, jwks_uri: str) -> PyJWKClient:
        client = _JWK_CLIENTS.get(jwks_uri)
        if client is None:
            client = PyJWKClient(jwks_uri)
            _JWK_CLIENTS[jwks_uri] = client
        return client

    async def _resolve_sso_user(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
    ) -> User:
        if not email_verified:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Email not verified by identity provider",
            )

        canonical = normalise_email(email)
        user = await self._users.get_by_sso_identity(provider, subject)
        if user is None:
            user = await self._users.get_by_email(canonical)
            if user is None:
                user = User(
                    email=email.strip(),
                    password_hash=None,
                    role=UserRole.MEMBER,
                    is_active=True,
                    sso_provider=provider,
                    sso_subject=subject,
                )
                self.session.add(user)
                await self.session.flush()
                await self.session.refresh(user)
            else:
                if not user.is_active:
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        detail="User account is disabled",
                    )
                user.sso_provider = provider
                user.sso_subject = subject
                if user.email_canonical != canonical:
                    user.email = email.strip()
                await self.session.flush()
        else:
            if not user.is_active:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User account is disabled")
            if user.email_canonical != canonical:
                user.email = email.strip()
                await self.session.flush()

        return user


__all__ = [
    "APIKeyIssueResult",
    "AuthenticatedIdentity",
    "AuthService",
    "OIDCProviderMetadata",
    "SSOLoginChallenge",
    "SSO_STATE_COOKIE",
    "hash_password",
    "normalise_email",
]
