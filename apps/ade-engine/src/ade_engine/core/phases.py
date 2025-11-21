"""Shared pipeline/job phase markers."""

from __future__ import annotations

from enum import Enum
from typing import Literal

JobStatus = Literal["succeeded", "failed"]


class PipelinePhase(str, Enum):
    """Recognized pipeline phases."""

    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    BEFORE_SAVE = "before_save"
    WRITING_OUTPUT = "writing_output"
    COMPLETED = "completed"
    FAILED = "failed"


__all__ = ["JobStatus", "PipelinePhase"]
