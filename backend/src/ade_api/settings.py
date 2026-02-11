"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings

from settings import (
    BlobStorageSettingsMixin,
    DatabaseSettingsMixin,
    DataPathsSettingsMixin,
    ade_settings_config,
    create_settings_accessors,
    normalize_log_format,
    normalize_log_level,
)

# ---- Defaults ---------------------------------------------------------------

DEFAULT_PUBLIC_WEB_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS: list[str] = []

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 2000
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
MAX_SET_SIZE = 50  # cap for *_in lists
COUNT_STATEMENT_TIMEOUT_MS: int | None = None  # optional (Postgres), e.g., 500

REMOVED_AUTH_ENV_VARS = (
    "ADE_AUTH_EXTERNAL_ENABLED",
    "ADE_AUTH_FORCE_SSO",
    "ADE_AUTH_SSO_AUTO_PROVISION",
    "ADE_AUTH_ENFORCE_LOCAL_MFA",
)


# ---- Settings ---------------------------------------------------------------


class Settings(
    DataPathsSettingsMixin,
    BlobStorageSettingsMixin,
    DatabaseSettingsMixin,
    BaseSettings,
):
    """FastAPI settings loaded from ADE_* environment variables."""

    model_config = ade_settings_config(enable_decoding=False, populate_by_name=True)

    # Core
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "unknown"
    app_commit_sha: str = "unknown"
    api_docs_enabled: bool = False
    api_docs_access_mode: Literal["authenticated", "public"] = "authenticated"
    docs_url: str = "/api/swagger"
    redoc_url: str = "/api"
    openapi_url: str = "/api/openapi.json"
    log_format: str = "console"
    log_level: str = "INFO"
    api_log_level: str | None = None
    request_log_level: str | None = None
    access_log_enabled: bool = True
    access_log_level: str | None = None
    safe_mode: bool = False

    # Server
    public_web_url: str = DEFAULT_PUBLIC_WEB_URL
    api_host: str | None = None
    api_processes: int | None = Field(default=None, ge=1)
    api_proxy_headers_enabled: bool = True
    api_forwarded_allow_ips: str = "127.0.0.1"
    api_threadpool_tokens: int = Field(40, ge=1)
    web_version_file: Path = Field(default=Path("/usr/share/nginx/html/version.json"))
    server_cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))
    server_cors_origin_regex: str | None = Field(default=None)

    # Storage
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    config_import_max_bytes: int = Field(50 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    documents_upload_concurrency_limit: int | None = Field(8, ge=1)

    # Database
    database_log_level: str | None = None
    database_connection_budget: int | None = Field(default=None, ge=1)
    document_changes_retention_days: int = Field(default=14, ge=1)

    # JWT
    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(30, ge=1)

    # Sessions
    session_cookie_name: str = "ade_session"
    session_csrf_cookie_name: str = "ade_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_access_ttl: timedelta = Field(default=timedelta(days=14))

    # Auth policy
    api_key_prefix_length: int = Field(12, ge=6, le=32)
    api_key_secret_bytes: int = Field(32, ge=16, le=128)
    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))
    allow_public_registration: bool = False
    auth_disabled: bool = False
    auth_disabled_user_email: str = "developer@example.com"
    auth_disabled_user_name: str | None = "Development User"
    auth_mode: str = "password_only"
    auth_password_reset_enabled: bool = True
    auth_password_mfa_required: bool = False
    auth_password_min_length: int = Field(12, ge=8, le=128)
    auth_password_require_uppercase: bool = False
    auth_password_require_lowercase: bool = False
    auth_password_require_number: bool = False
    auth_password_require_symbol: bool = False
    auth_password_lockout_max_attempts: int = Field(5, ge=1, le=20)
    auth_password_lockout_duration_seconds: int = Field(300, ge=30, le=86_400)
    auth_idp_jit_provisioning_enabled: bool = True
    auth_sso_providers_json: str | None = None
    sso_encryption_key: SecretStr | None = None

    # Runs
    preview_timeout_seconds: float = Field(10, gt=0)

    # ---- Validators ----

    @field_validator("server_cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return parsed
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(value, tuple):
            return list(value)
        return value

    @field_validator("api_forwarded_allow_ips", mode="before")
    @classmethod
    def _normalize_api_forwarded_allow_ips(cls, value: object) -> object:
        if value is None:
            return "127.0.0.1"
        raw = str(value).strip()
        if not raw:
            raise ValueError("ADE_API_FORWARDED_ALLOW_IPS must not be empty.")
        return raw

    @field_validator("api_docs_access_mode", mode="before")
    @classmethod
    def _normalize_api_docs_access_mode(cls, value: object) -> object:
        if value is None:
            return "authenticated"
        raw = str(value).strip().lower()
        if not raw:
            raise ValueError("ADE_API_DOCS_ACCESS_MODE must not be empty.")
        return raw

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        self.log_format = normalize_log_format(self.log_format, env_var="ADE_LOG_FORMAT")

        normalized_log_level = normalize_log_level(self.log_level, env_var="ADE_LOG_LEVEL")
        if normalized_log_level is None:
            raise ValueError("ADE_LOG_LEVEL must not be empty.")
        self.log_level = normalized_log_level

        self.api_log_level = normalize_log_level(self.api_log_level, env_var="ADE_API_LOG_LEVEL")
        self.request_log_level = normalize_log_level(
            self.request_log_level,
            env_var="ADE_REQUEST_LOG_LEVEL",
        )
        self.access_log_level = normalize_log_level(
            self.access_log_level,
            env_var="ADE_ACCESS_LOG_LEVEL",
        )
        self.database_log_level = normalize_log_level(
            self.database_log_level,
            env_var="ADE_DATABASE_LOG_LEVEL",
        )

        mode = (self.auth_mode or "").strip().lower()
        if mode not in {"password_only", "idp_only", "password_and_idp"}:
            raise ValueError(
                "ADE_AUTH_MODE must be one of: password_only, idp_only, password_and_idp."
            )
        self.auth_mode = mode

        removed_set = sorted(
            env_name for env_name in REMOVED_AUTH_ENV_VARS if os.getenv(env_name) not in (None, "")
        )
        if removed_set:
            raise ValueError(
                "Removed auth environment variables are no longer supported: "
                + ", ".join(removed_set)
                + (
                    ". Use ADE_AUTH_MODE, ADE_AUTH_PASSWORD_*, and "
                    "ADE_AUTH_IDP_JIT_PROVISIONING_ENABLED."
                )
            )

        if self.algorithm != "HS256":
            raise ValueError("ADE_ALGORITHM must be HS256.")
        if len(self.secret_key.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("ADE_SECRET_KEY must be at least 32 bytes (recommend 64+).")
        if self.server_cors_origin_regex:
            re.compile(self.server_cors_origin_regex)
        return self

    # ---- Convenience ----

    @property
    def effective_api_log_level(self) -> str:
        return self.api_log_level or self.log_level

    @property
    def runs_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def effective_request_log_level(self) -> str:
        return self.request_log_level or self.effective_api_log_level

    @property
    def effective_access_log_level(self) -> str:
        return self.access_log_level or self.effective_api_log_level

    @property
    def secret_key_value(self) -> str:
        return self.secret_key.get_secret_value()


get_settings, reload_settings = create_settings_accessors(Settings)


__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_PUBLIC_WEB_URL",
    "Settings",
    "get_settings",
    "reload_settings",
]
