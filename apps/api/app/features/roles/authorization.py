"""Unified authorization entrypoint bridging legacy helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Principal, ScopeType
from .service import (
    AuthorizationDecision,
    AuthorizationError,
    authorize_global,
    get_global_permissions_for_principal,
    get_workspace_permissions_for_principal,
)

async def authorize(
    *,
    session: AsyncSession,
    principal_id: str,
    permission_key: str,
    scope_type: ScopeType = ScopeType.GLOBAL,
    scope_id: str | None = None,
) -> AuthorizationDecision:
    """Evaluate the permission requirement for the referenced principal."""

    principal = await session.get(Principal, principal_id)
    if principal is None:
        return AuthorizationDecision(
            granted=frozenset(),
            required=(permission_key,),
            missing=(permission_key,),
        )

    if scope_type == ScopeType.GLOBAL:
        granted = await get_global_permissions_for_principal(
            session=session, principal=principal
        )
        decision = authorize_global(granted=granted, required=[permission_key])
        return decision

    if scope_type == ScopeType.WORKSPACE:
        if scope_id is None:
            msg = "scope_id is required for workspace authorization"
            raise AuthorizationError(msg)

        granted = await get_workspace_permissions_for_principal(
            session=session, principal=principal, workspace_id=scope_id
        )
        missing: tuple[str, ...]
        if permission_key in granted:
            missing = ()
        else:
            missing = (permission_key,)
        return AuthorizationDecision(
            granted=granted,
            required=(permission_key,),
            missing=missing,
        )

    msg = f"Unsupported scope_type '{scope_type}'"
    raise AuthorizationError(msg)


__all__ = ["ScopeType", "authorize"]
