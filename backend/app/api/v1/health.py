from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {
        "ok": "true",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", tags=["health"])
async def ready() -> dict[str, str]:
    # In the future check downstream dependencies (DB, message bus, etc.).
    return {
        "ok": "true",
        "status": "ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/v1/healthz", tags=["health"])
async def versioned_health() -> dict[str, str]:
    return {"ok": "true", "status": "healthy", "version": "v1"}
