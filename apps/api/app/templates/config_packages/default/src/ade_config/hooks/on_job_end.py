"""Emit a simple summary when the job finishes."""

from __future__ import annotations

from typing import Any, Mapping


def run(*, artifact: Mapping[str, Any] | None = None, note=None, **_: Any) -> None:
    tables = 0
    if artifact:
        for sheet in artifact.get("sheets", []):
            tables += len(sheet.get("tables", []))
    message = f"Job completed with {tables} table(s) processed."
    if note is not None:
        note("job_end", message)
