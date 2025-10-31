"""Shared dataclasses used across job orchestration modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ResolvedInput:
    """Describes an input document staged for a job run."""

    document_id: str
    source_path: Path
    filename: str
    sha256: str


__all__ = ["ResolvedInput"]
