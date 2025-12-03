from __future__ import annotations

from sqlalchemy import func

from ade_api.common.sql import nulls_last
from ade_api.core.models import User

SORT_FIELDS = {
    "id": (User.id.asc(), User.id.desc()),
    "email": (
        func.lower(User.email).asc(),
        func.lower(User.email).desc(),
    ),
    "display_name": (
        tuple(nulls_last(func.lower(User.display_name).asc())),
        tuple(nulls_last(func.lower(User.display_name).desc())),
    ),
    "created_at": (User.created_at.asc(), User.created_at.desc()),
    "updated_at": (User.updated_at.asc(), User.updated_at.desc()),
    "last_login_at": (
        tuple(nulls_last(User.last_login_at.asc())),
        tuple(nulls_last(User.last_login_at.desc())),
    ),
    "failed_login_count": (User.failed_login_count.asc(), User.failed_login_count.desc()),
    "is_active": (User.is_active.asc(), User.is_active.desc()),
    "is_service_account": (
        User.is_service_account.asc(),
        User.is_service_account.desc(),
    ),
}

DEFAULT_SORT = ["email"]
ID_FIELD = (User.id.asc(), User.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
