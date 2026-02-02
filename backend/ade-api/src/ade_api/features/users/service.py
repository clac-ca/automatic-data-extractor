"""Business logic for user operations."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.cursor_listing import ResolvedCursorSort, paginate_query_cursor
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.core.security.hashing import hash_password
from ade_api.features.api_keys.service import ApiKeyService
from ade_api.features.rbac import RbacService
from ade_db.models import User
from ade_api.settings import Settings

from .filters import apply_user_filters
from .repository import UsersRepository
from .schemas import UserOut, UserPage, UserProfile, UserUpdate

logger = logging.getLogger(__name__)
LOCKOUT_HORIZON = timedelta(days=365 * 10)


class UsersService:
    """Expose read-oriented helpers for user accounts."""

    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._repo = UsersRepository(session)
        self._api_keys = ApiKeyService(session=session, settings=settings)

    def get_profile(self, *, user: User) -> UserProfile:
        """Return the profile for the authenticated user."""
        logger.debug(
            "user.profile.get.start",
            extra=log_context(user_id=str(user.id)),
        )

        profile = self._build_profile(user)

        logger.debug(
            "user.profile.get.success",
            extra=log_context(user_id=str(user.id)),
        )
        return profile

    def get_user(self, *, user_id: str | UUID) -> UserOut:
        """Return a single user profile by identifier."""

        logger.debug(
            "users.get.start",
            extra=log_context(user_id=str(user_id)),
        )

        user = self._repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        result = self._serialize_user(user)
        logger.info(
            "users.get.success",
            extra=log_context(user_id=str(user.id)),
        )
        return result

    def list_users(
        self,
        *,
        limit: int,
        cursor: str | None,
        resolved_sort: ResolvedCursorSort[User],
        include_total: bool,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
    ) -> UserPage:
        """Return paginated users according to the supplied parameters."""

        logger.debug(
            "users.list.start",
            extra=log_context(
                limit=limit,
                cursor=cursor,
                order_by=str(resolved_sort.order_by),
                q=q,
            ),
        )

        stmt = select(User)
        stmt = apply_user_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )
        page_result = paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

        items: list[UserOut] = []
        for user in page_result.items:
            items.append(self._serialize_user(user))

        result = UserPage(items=items, meta=page_result.meta, facets=page_result.facets)

        logger.info(
            "users.list.success",
            extra=log_context(
                limit=result.meta.limit,
                count=len(result.items),
                total=result.meta.total_count,
            ),
        )
        return result

    def update_user(
        self,
        *,
        user_id: str | UUID,
        payload: UserUpdate,
        actor: User | None = None,
    ) -> UserOut:
        """Update mutable user fields."""

        logger.debug(
            "users.update.start",
            extra=log_context(user_id=str(user_id)),
        )

        user = self._repo.get_by_id_basic(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        updates = payload.model_dump(exclude_unset=True, exclude_none=False)
        if not updates:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one field to update.",
            )
        if "is_active" in updates and updates["is_active"] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="is_active must be true or false when provided.",
            )

        repo_kwargs = {}
        if "display_name" in updates:
            repo_kwargs["display_name"] = updates["display_name"]
        is_active_update = updates.get("is_active")

        if is_active_update is False and (user.is_active or user.locked_until is None):
            if actor is not None and actor.id == user.id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Users cannot deactivate their own account.",
                )
            self._apply_deactivation(user=user, actor=actor)
        elif is_active_update is True and not user.is_active:
            self._apply_reactivation(user=user)
        elif "is_active" in updates:
            repo_kwargs["is_active"] = updates["is_active"]

        if repo_kwargs:
            self._repo.update_user(
                user,
                **repo_kwargs,
            )

        result = self._serialize_user(user)
        logger.info(
            "users.update.success",
            extra=log_context(
                user_id=str(user.id),
                is_active=user.is_active,
                has_display_name=bool(user.display_name),
            ),
        )
        return result

    def deactivate_user(
        self,
        *,
        user_id: str | UUID,
        actor: User,
    ) -> UserOut:
        """Deactivate a user account and revoke API keys."""

        user = self._repo.get_by_id_basic(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if actor.id == user.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Users cannot deactivate their own account.",
            )

        self._apply_deactivation(user=user, actor=actor)
        return self._serialize_user(user)

    def _build_profile(self, user: User) -> UserProfile:
        logger.debug(
            "user.profile.build",
            extra=log_context(user_id=str(user.id)),
        )

        rbac = RbacService(session=self._session)
        permissions = rbac.get_global_permissions_for_user(user=user)
        roles = rbac.get_global_role_slugs_for_user(user=user)
        return UserProfile(
            id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_service_account=user.is_service_account,
            display_name=user.display_name,
            roles=sorted(roles),
            permissions=sorted(permissions),
        )

    def _serialize_user(self, user: User) -> UserOut:
        profile = self._build_profile(user)
        return UserOut(
            **profile.model_dump(),
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _apply_deactivation(self, *, user: User, actor: User | None) -> None:
        now = utc_now()
        user.is_active = False
        user.locked_until = now + LOCKOUT_HORIZON
        user.failed_login_count = 0
        self._session.flush()
        self._api_keys.revoke_all_for_user(user_id=user.id)
        logger.info(
            "users.deactivate",
            extra=log_context(
                user_id=str(user.id),
                actor_id=str(actor.id) if actor else None,
                locked_until=str(user.locked_until) if user.locked_until else None,
            ),
        )

    def _apply_reactivation(self, *, user: User) -> None:
        user.is_active = True
        user.locked_until = None
        user.failed_login_count = 0
        self._session.flush()

    def create_admin(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> User:
        """Create an administrator account with the supplied credentials."""

        canonical_email = email.strip().lower()
        # Avoid logging full email; optionally log the domain for debugging.
        email_domain: str | None = None
        if "@" in canonical_email:
            _, email_domain = canonical_email.rsplit("@", 1)

        logger.debug(
            "user.admin.create.start",
            extra=log_context(
                email_domain=email_domain,
                has_display_name=bool(display_name),
            ),
        )

        existing = self._repo.get_by_email(canonical_email)
        if existing is not None:
            logger.warning(
                "user.admin.create.conflict_existing",
                extra=log_context(
                    user_id=str(existing.id),
                    email_domain=email_domain,
                ),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )

        password_hash = hash_password(password)
        cleaned_display_name = display_name.strip() if display_name else None

        try:
            user = self._repo.create(
                email=canonical_email,
                hashed_password=password_hash,
                display_name=cleaned_display_name,
                is_active=True,
                is_service_account=False,
                is_superuser=True,
                is_verified=True,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            logger.warning(
                "user.admin.create.integrity_conflict",
                extra=log_context(
                    email_domain=email_domain,
                    has_display_name=bool(display_name),
                ),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            ) from exc

        logger.info(
            "user.admin.create.success",
            extra=log_context(
                user_id=str(user.id),
                email_domain=email_domain,
                is_active=user.is_active,
                is_service_account=user.is_service_account,
                has_display_name=bool(cleaned_display_name),
            ),
        )
        return user


__all__ = ["UsersService"]
