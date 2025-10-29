"""Placeholder router for configuration engine v0.4 implementation."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/workspaces/{workspace_id}/configs", tags=["configs"])

__all__ = ["router"]
