from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from ...core.service import BaseService, ServiceContext
from ..service_accounts.models import ServiceAccount
from ..service_accounts.repository import ServiceAccountsRepository
from ..users.models import User, UserRole
from ..users.repository import UsersRepository
from .models import APIKey
from .repository import APIKeysRepository
from .security import (
    TokenPayload,
    create_access_token,
    decode_access_token,
    generate_api_key_components,
    hash_api_key,
    hash_password,
    verify_password,
)


@dataclass(slots=True)
class APIKeyIssueResult:
    """Result returned when issuing an API key."""

    raw_key: str
    api_key: APIKey
    principal_type: APIKeyPrincipalType
    user: User | None = None
    service_account: ServiceAccount | None = None


class APIKeyPrincipalType(StrEnum):
    """Supported principals that can own API keys."""

    USER = "user"
    SERVICE_ACCOUNT = "service_account"


@dataclass(slots=True)
class AuthenticatedPrincipal:
    """Principal resolved during authentication."""

    principal_type: APIKeyPrincipalType
    api_key: APIKey | None = None
    user: User | None = None
    service_account: ServiceAccount | None = None

    @property
    def label(self) -> str:
        if self.principal_type == APIKeyPrincipalType.USER and self.user is not None:
            return self.user.email
        if (
            self.principal_type == APIKeyPrincipalType.SERVICE_ACCOUNT
            and self.service_account is not None
        ):
            return self.service_account.display_name
        return "unknown"


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
        self._service_accounts = ServiceAccountsRepository(self.session)
        self._api_keys = APIKeysRepository(self.session)

    # ------------------------------------------------------------------
    # Password-based authentication

    async def authenticate(self, *, email: str, password: str) -> User:
        """Return the active user matching ``email``/``password``."""

        canonical = normalise_email(email)
        user = await self._users.get_by_email(canonical)
        if user is None or not user.password_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        return user

    async def issue_token(self, user: User) -> str:
        """Return a signed token for ``user``."""

        expires = timedelta(minutes=self.settings.auth_token_exp_minutes)
        return create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            secret=self.settings.auth_token_secret,
            algorithm=self.settings.auth_token_algorithm,
            expires_delta=expires,
        )

    def decode_token(self, token: str) -> TokenPayload:
        """Decode ``token`` and return its payload."""

        return decode_access_token(
            token=token,
            secret=self.settings.auth_token_secret,
            algorithms=[self.settings.auth_token_algorithm],
        )

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
        user: User | None = None,
        service_account: ServiceAccount | None = None,
        expires_at: datetime | None = None,
    ) -> APIKeyIssueResult:
        """Persist an API key for the supplied principal and return the raw secret."""

        if (user is None) == (service_account is None):
            msg = "Exactly one principal must be provided"
            raise ValueError(msg)

        prefix, secret = generate_api_key_components()
        token_hash = hash_api_key(secret)
        record = await self._api_keys.create(
            user_id=user.id if user else None,
            service_account_id=service_account.id if service_account else None,
            token_prefix=prefix,
            token_hash=token_hash,
            expires_at=expires_at.isoformat(timespec="seconds") if expires_at else None,
        )
        principal_type = (
            APIKeyPrincipalType.USER if user is not None else APIKeyPrincipalType.SERVICE_ACCOUNT
        )
        return APIKeyIssueResult(
            raw_key=f"{prefix}.{secret}",
            api_key=record,
            principal_type=principal_type,
            user=user,
            service_account=service_account,
        )

    async def issue_api_key_for_service_account(
        self,
        *,
        service_account_id: str,
        expires_in_days: int | None = None,
    ) -> APIKeyIssueResult:
        """Issue an API key for the service account identified by ``service_account_id``."""

        record = await self._service_accounts.get_by_id(service_account_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Service account not found")
        if not record.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Target service account is inactive",
            )

        expires_at = None
        if expires_in_days is not None:
            expires_at = self._now() + timedelta(days=expires_in_days)

        return await self.issue_api_key(service_account=record, expires_at=expires_at)

    async def list_api_keys(self) -> list[APIKey]:
        """Return all issued API keys ordered by creation time."""

        return await self._api_keys.list_api_keys()

    async def revoke_api_key(self, api_key_id: str) -> None:
        """Remove the API key identified by ``api_key_id``."""

        record = await self._api_keys.get_by_id(api_key_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
        await self._api_keys.delete(record)

    async def authenticate_api_key(self, raw_key: str) -> AuthenticatedPrincipal:
        """Return the principal associated with ``raw_key`` if valid."""

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

        principal: AuthenticatedPrincipal | None = None
        if record.user_id:
            user = record.user
            if user is None:
                user = await self._users.get_by_id(record.user_id)
            if user is None or not user.is_active:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
            principal = AuthenticatedPrincipal(
                principal_type=APIKeyPrincipalType.USER,
                api_key=record,
                user=user,
            )
        elif record.service_account_id:
            account = record.service_account
            if account is None:
                account = await self._service_accounts.get_by_id(record.service_account_id)
            if account is None or not account.is_active:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
            principal = AuthenticatedPrincipal(
                principal_type=APIKeyPrincipalType.SERVICE_ACCOUNT,
                api_key=record,
                service_account=account,
            )
        else:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        request = self.request
        if request is not None:
            await self._touch_api_key(record, request=request)
        if principal is None:  # pragma: no cover - defensive safety net
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return principal

    async def _touch_api_key(self, record: APIKey, *, request: Request) -> None:
        interval = self.settings.api_key_touch_interval_seconds
        now = self._now()
        last_seen = self._parse_timestamp(record.last_seen_at)
        if interval > 0 and last_seen is not None:
            if (now - last_seen).total_seconds() < interval:
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

        if not self.settings.sso_enabled:
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
            "client_id": self.settings.sso_client_id,
            "redirect_uri": self.settings.sso_redirect_url,
            "scope": self.settings.sso_scope,
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

        secret = self.settings.auth_token_secret
        if not secret:
            raise RuntimeError(
                "auth_token_secret must be configured when authentication is enabled",
            )

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[self.settings.auth_token_algorithm],
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

        id_claims = self._verify_jwt_via_jwks(
            token=id_token,
            jwks_uri=metadata.jwks_uri,
            audience=self.settings.sso_client_id,
            issuer=self.settings.sso_issuer or "",
            nonce=stored_state.nonce,
        )

        resource_audience = self.settings.sso_resource_audience
        if resource_audience:
            self._verify_jwt_via_jwks(
                token=access_token,
                jwks_uri=metadata.jwks_uri,
                audience=resource_audience,
                issuer=self.settings.sso_issuer or "",
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
            provider=self.settings.sso_issuer or "",
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
        secret = self.settings.auth_token_secret
        if not secret:
            raise RuntimeError(
                "auth_token_secret must be configured when authentication is enabled",
            )

        payload = {
            "state": state,
            "code_verifier": code_verifier,
            "nonce": nonce,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + timedelta(seconds=_SSO_STATE_TTL_SECONDS)).timestamp()),
        }
        return jwt.encode(payload, secret, algorithm=self.settings.auth_token_algorithm)

    async def _get_oidc_metadata(self) -> OIDCProviderMetadata:
        issuer = self.settings.sso_issuer or ""
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
            "redirect_uri": self.settings.sso_redirect_url,
            "code_verifier": code_verifier,
            "client_id": self.settings.sso_client_id,
        }

        auth: tuple[str, str] | None = None
        if self.settings.sso_client_secret:
            auth = (self.settings.sso_client_id or "", self.settings.sso_client_secret)
            payload["client_secret"] = self.settings.sso_client_secret

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
    "APIKeyPrincipalType",
    "AuthenticatedPrincipal",
    "AuthService",
    "OIDCProviderMetadata",
    "SSOLoginChallenge",
    "SSO_STATE_COOKIE",
    "hash_password",
    "normalise_email",
]
