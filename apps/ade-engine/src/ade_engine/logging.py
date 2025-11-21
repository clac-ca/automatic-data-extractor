"""Compatibility shim for legacy StructuredLogger imports."""

from ade_engine.telemetry.logging import PipelineLogger

StructuredLogger = PipelineLogger

__all__ = ["PipelineLogger", "StructuredLogger"]
