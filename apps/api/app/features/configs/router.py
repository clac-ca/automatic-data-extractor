"""Configs router placeholder."""

from fastapi import APIRouter

router = APIRouter(prefix="/configs", tags=["configs"])

__all__ = ["router"]
