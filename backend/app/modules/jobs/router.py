"""Placeholder router for the rebuilt jobs module."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", include_in_schema=False)
async def jobs_placeholder() -> None:
    """Placeholder endpoint signalling that the module is being rewritten."""

    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "The jobs module is being rewritten. See BACKEND_REWRITE_PLAN.md for "
            "the upcoming design."
        ),
    )


__all__ = ["router"]

