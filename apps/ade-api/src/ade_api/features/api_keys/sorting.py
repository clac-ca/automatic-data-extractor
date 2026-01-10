from __future__ import annotations

from sqlalchemy import func

from ade_api.common.sql import nulls_last
from ade_api.models import ApiKey

SORT_FIELDS = {
    "id": (ApiKey.id.asc(), ApiKey.id.desc()),
    "createdAt": (ApiKey.created_at.asc(), ApiKey.created_at.desc()),
    "expiresAt": (
        tuple(nulls_last(ApiKey.expires_at.asc())),
        tuple(nulls_last(ApiKey.expires_at.desc())),
    ),
    "revokedAt": (
        tuple(nulls_last(ApiKey.revoked_at.asc())),
        tuple(nulls_last(ApiKey.revoked_at.desc())),
    ),
    "lastUsedAt": (
        tuple(nulls_last(ApiKey.last_used_at.asc())),
        tuple(nulls_last(ApiKey.last_used_at.desc())),
    ),
    "name": (
        tuple(nulls_last(func.lower(ApiKey.name).asc())),
        tuple(nulls_last(func.lower(ApiKey.name).desc())),
    ),
    "prefix": (ApiKey.prefix.asc(), ApiKey.prefix.desc()),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (ApiKey.id.asc(), ApiKey.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
