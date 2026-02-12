from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.core.security import hash_opaque_token, mint_opaque_token
from ade_db.models import ScimToken, User

from .schemas import (
    ScimTokenCreateRequest,
    ScimTokenCreateResponse,
    ScimTokenListResponse,
    ScimTokenOut,
)


class ScimTokenService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    @staticmethod
    def _serialize(item: ScimToken) -> ScimTokenOut:
        return ScimTokenOut(
            id=item.id,
            name=item.name,
            prefix=item.prefix,
            created_by_user_id=item.created_by_user_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            last_used_at=item.last_used_at,
            revoked_at=item.revoked_at,
        )

    def list_tokens(self) -> ScimTokenListResponse:
        stmt = select(ScimToken).order_by(ScimToken.created_at.desc(), ScimToken.id.desc())
        items = list(self._session.execute(stmt).scalars().all())
        return ScimTokenListResponse(items=[self._serialize(item) for item in items])

    def create_token(
        self, *, payload: ScimTokenCreateRequest, actor: User
    ) -> ScimTokenCreateResponse:
        token = f"scim_{mint_opaque_token(48)}"
        prefix = token[:16]

        item = ScimToken(
            name=payload.name.strip(),
            prefix=prefix,
            hashed_secret=hash_opaque_token(token),
            created_by_user_id=actor.id,
        )
        self._session.add(item)
        try:
            self._session.flush([item])
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Failed to issue SCIM token due to a uniqueness conflict",
            ) from exc
        return ScimTokenCreateResponse(token=token, item=self._serialize(item))

    def revoke_token(self, *, token_id: UUID) -> ScimTokenOut:
        item = self._session.get(ScimToken, token_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="SCIM token not found"
            )
        if item.revoked_at is None:
            item.revoked_at = utc_now()
            self._session.flush([item])
        return self._serialize(item)

    def authenticate_bearer_token(self, *, token: str) -> ScimToken:
        hashed = hash_opaque_token(token)
        item = self._session.execute(
            select(ScimToken)
            .where(ScimToken.hashed_secret == hashed)
            .where(ScimToken.revoked_at.is_(None))
            .limit(1)
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM token"
            )

        item.last_used_at = utc_now()
        self._session.flush([item])
        return item


__all__ = ["ScimTokenService"]
