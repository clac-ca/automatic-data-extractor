"""Local development profile helpers for ADE CLI."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from paths import REPO_ROOT

DEFAULT_LOCAL_PROFILE_SPAN = 1000
DEFAULT_DB_PORT_BASE = 15432
DEFAULT_BLOB_PORT_BASE = 20000
DEFAULT_WEB_PORT_BASE = 30000
DEFAULT_API_PORT_BASE = 31000
DEFAULT_SECRET_KEY = "dev-only-unsafe-secret-key-change-me-please-0000000000000000"
DEFAULT_POSTGRES_USER = "ade"
DEFAULT_POSTGRES_PASSWORD = "ade"
DEFAULT_POSTGRES_DB = "ade"
DEFAULT_BLOB_CONTAINER = "ade"
DEFAULT_BLOB_PREFIX = "workspaces"
DEFAULT_AZURITE_ACCOUNTS = (
    "devstoreaccount1:"
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw=="
)

LOCAL_ENV_PATH = REPO_ROOT / ".env"

REQUIRED_LOCAL_ENV_KEYS = frozenset(
    {
        "ADE_LOCAL_PROFILE_ID",
        "COMPOSE_PROJECT_NAME",
        "ADE_LOCAL_DB_PORT",
        "ADE_LOCAL_BLOB_PORT",
        "ADE_API_PORT",
        "ADE_WEB_PORT",
        "ADE_DATABASE_URL",
        "ADE_BLOB_CONNECTION_STRING",
        "ADE_BLOB_CONNECTION_STRING_DOCKER",
        "ADE_BLOB_CONTAINER",
        "ADE_SECRET_KEY",
        "ADE_AUTH_DISABLED",
        "ADE_PUBLIC_WEB_URL",
        "ADE_INTERNAL_API_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "AZURITE_ACCOUNTS",
    }
)


@dataclass(frozen=True)
class LocalProfile:
    profile_id: str
    project_name: str
    db_port: int
    blob_port: int
    web_port: int
    api_port: int


@dataclass(frozen=True)
class LocalEnvResult:
    profile: LocalProfile
    values: dict[str, str]
    path: Path
    wrote_file: bool


def _profile_hash(repo_root: Path) -> str:
    canonical = str(repo_root.resolve())
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:8]


def _sanitize_project_name(raw: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-_")
    if normalized:
        return normalized
    return "ade"


def _derive_port(base: int, offset: int) -> int:
    return base + offset


def build_local_profile(*, repo_root: Path = REPO_ROOT) -> LocalProfile:
    profile_id = _profile_hash(repo_root)
    offset = int(profile_id, 16) % DEFAULT_LOCAL_PROFILE_SPAN
    project_name = f"{_sanitize_project_name(repo_root.name)}-{profile_id}"
    return LocalProfile(
        profile_id=profile_id,
        project_name=project_name,
        db_port=_derive_port(DEFAULT_DB_PORT_BASE, offset),
        blob_port=_derive_port(DEFAULT_BLOB_PORT_BASE, offset),
        web_port=_derive_port(DEFAULT_WEB_PORT_BASE, offset),
        api_port=_derive_port(DEFAULT_API_PORT_BASE, offset),
    )


def _default_local_env_map(profile: LocalProfile) -> dict[str, str]:
    return {
        "ADE_LOCAL_PROFILE_ID": profile.profile_id,
        "COMPOSE_PROJECT_NAME": profile.project_name,
        "ADE_LOCAL_DB_PORT": str(profile.db_port),
        "ADE_LOCAL_BLOB_PORT": str(profile.blob_port),
        "ADE_API_PORT": str(profile.api_port),
        "ADE_WEB_PORT": str(profile.web_port),
        "POSTGRES_USER": DEFAULT_POSTGRES_USER,
        "POSTGRES_PASSWORD": DEFAULT_POSTGRES_PASSWORD,
        "POSTGRES_DB": DEFAULT_POSTGRES_DB,
        "AZURITE_ACCOUNTS": DEFAULT_AZURITE_ACCOUNTS,
        "ADE_DATABASE_URL": (
            f"postgresql+psycopg://{DEFAULT_POSTGRES_USER}:{DEFAULT_POSTGRES_PASSWORD}"
            f"@127.0.0.1:{profile.db_port}/{DEFAULT_POSTGRES_DB}?sslmode=disable"
        ),
        "ADE_BLOB_CONNECTION_STRING": (
            "DefaultEndpointsProtocol=http;"
            "AccountName=devstoreaccount1;"
            "AccountKey="
            "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
            "K1SZFPTOtr/KBHBeksoGMGw==;"
            f"BlobEndpoint=http://127.0.0.1:{profile.blob_port}/devstoreaccount1;"
        ),
        "ADE_BLOB_CONNECTION_STRING_DOCKER": (
            "DefaultEndpointsProtocol=http;"
            "AccountName=devstoreaccount1;"
            "AccountKey="
            "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
            "K1SZFPTOtr/KBHBeksoGMGw==;"
            "BlobEndpoint=http://blob:10000/devstoreaccount1;"
        ),
        "ADE_BLOB_CONTAINER": DEFAULT_BLOB_CONTAINER,
        "ADE_BLOB_PREFIX": DEFAULT_BLOB_PREFIX,
        "ADE_SECRET_KEY": DEFAULT_SECRET_KEY,
        "ADE_AUTH_DISABLED": "true",
        "ADE_PUBLIC_WEB_URL": f"http://127.0.0.1:{profile.web_port}",
        "ADE_INTERNAL_API_URL": f"http://127.0.0.1:{profile.api_port}",
    }


def _read_local_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for key, value in dotenv_values(path).items():
        if value is None:
            continue
        values[str(key)] = value
    return values


def _has_required_keys(values: dict[str, str]) -> bool:
    missing = REQUIRED_LOCAL_ENV_KEYS.difference(values)
    return not missing


def _write_local_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Auto-generated/updated by `ade infra up` for local native development.",
        "# Re-run `ade infra up --force` to regenerate deterministic defaults for this worktree.",
        "",
    ]
    for key in sorted(values):
        lines.append(f"{key}={values[key]}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def ensure_local_env(
    *,
    force: bool = False,
    repo_root: Path = REPO_ROOT,
    path: Path = LOCAL_ENV_PATH,
) -> LocalEnvResult:
    profile = build_local_profile(repo_root=repo_root)
    defaults = _default_local_env_map(profile)
    existing = _read_local_env(path)
    profile_mismatch = existing.get("ADE_LOCAL_PROFILE_ID") != profile.profile_id
    should_write = (
        force
        or not path.exists()
        or not _has_required_keys(existing)
        or profile_mismatch
    )

    if should_write:
        merged = dict(existing)
        merged.update(defaults)
        _write_local_env(path, merged)
        values = merged
    else:
        values = existing

    return LocalEnvResult(
        profile=profile,
        values=values,
        path=path,
        wrote_file=should_write,
    )


def load_local_env(path: Path = LOCAL_ENV_PATH) -> bool:
    """Load repo-root .env into process environment (non-overriding)."""

    if not path.exists():
        return False
    load_dotenv(path, override=False)
    return True


def local_env_exists(path: Path = LOCAL_ENV_PATH) -> bool:
    return path.exists()


def missing_core_runtime_env() -> list[str]:
    """Return missing core vars for native ADE runtime startup."""

    missing = [name for name in ("ADE_DATABASE_URL", "ADE_SECRET_KEY") if not os.getenv(name)]
    if not os.getenv("ADE_BLOB_CONNECTION_STRING") and not os.getenv("ADE_BLOB_ACCOUNT_URL"):
        missing.append("ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL")
    return missing
