from __future__ import annotations

from ade_api.common.sql import nulls_last
from ade_api.models import Configuration

SORT_FIELDS = {
    "id": (Configuration.id.asc(), Configuration.id.desc()),
    "displayName": (Configuration.display_name.asc(), Configuration.display_name.desc()),
    "status": (Configuration.status.asc(), Configuration.status.desc()),
    "createdAt": (Configuration.created_at.asc(), Configuration.created_at.desc()),
    "updatedAt": (Configuration.updated_at.asc(), Configuration.updated_at.desc()),
    "activatedAt": (
        tuple(nulls_last(Configuration.activated_at.asc())),
        tuple(nulls_last(Configuration.activated_at.desc())),
    ),
    "lastUsedAt": (
        tuple(nulls_last(Configuration.last_used_at.asc())),
        tuple(nulls_last(Configuration.last_used_at.desc())),
    ),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Configuration.id.asc(), Configuration.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
