from __future__ import annotations

from sqlalchemy import func

from ade_api.common.sql import nulls_last
from ade_api.models import User

SORT_FIELDS = {
    "id": (User.id.asc(), User.id.desc()),
    "email": (
        func.lower(User.email).asc(),
        func.lower(User.email).desc(),
    ),
    "displayName": (
        tuple(nulls_last(func.lower(User.display_name).asc())),
        tuple(nulls_last(func.lower(User.display_name).desc())),
    ),
    "createdAt": (User.created_at.asc(), User.created_at.desc()),
    "updatedAt": (User.updated_at.asc(), User.updated_at.desc()),
    "lastLoginAt": (
        tuple(nulls_last(User.last_login_at.asc())),
        tuple(nulls_last(User.last_login_at.desc())),
    ),
    "failedLoginCount": (User.failed_login_count.asc(), User.failed_login_count.desc()),
    "isActive": (User.is_active.asc(), User.is_active.desc()),
    "isServiceAccount": (
        User.is_service_account.asc(),
        User.is_service_account.desc(),
    ),
}

DEFAULT_SORT = ["email"]
ID_FIELD = (User.id.asc(), User.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
