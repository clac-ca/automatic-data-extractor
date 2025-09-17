"""Pydantic schemas for API responses and payloads."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


__all__ = ["HealthResponse"]
