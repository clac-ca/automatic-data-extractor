"""Shared Pydantic schemas for job representations."""

from __future__ import annotations

from typing import Literal

JobStatusLiteral = Literal["queued", "running", "succeeded", "failed", "cancelled"]

__all__ = ["JobStatusLiteral"]
