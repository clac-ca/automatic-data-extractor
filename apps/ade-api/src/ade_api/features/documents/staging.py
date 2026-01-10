"""Shared helpers for staging workspace documents into run directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.features.documents.storage import DocumentStorage
from ade_api.models import Document

__all__ = ["stage_document_input"]


def stage_document_input(
    *,
    document: Document,
    storage: DocumentStorage,
    session: Session,
    run_dir: Path,
) -> Path:
    """Copy ``document`` into ``run_dir/input`` and update access metadata."""

    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    source = storage.path_for(document.stored_uri)
    destination = input_dir / document.original_filename

    shutil.copy2(source, destination)
    document.last_run_at = utc_now()
    session.flush()

    return destination
