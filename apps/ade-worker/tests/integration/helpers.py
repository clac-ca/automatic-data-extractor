from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert

from ade_worker.schema import files, file_versions


def _uuid() -> str:
    return str(uuid4())


def seed_file_with_version(
    engine,
    *,
    workspace_id: str,
    name: str = "input.xlsx",
    kind: str = "input",
    now: datetime,
    doc_no: int | None = 1,
    parent_file_id: str | None = None,
    origin: str = "uploaded",
    content_type: str | None = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
) -> tuple[str, str]:
    file_id = _uuid()
    version_id = _uuid()
    blob_name = f"{workspace_id}/files/{file_id}"
    name_key = name.strip().lower() or "input.xlsx"
    expires_at = now + timedelta(days=30)

    with engine.begin() as conn:
        conn.execute(
            insert(files).values(
                id=file_id,
                workspace_id=workspace_id,
                kind=kind,
                doc_no=doc_no,
                name=name,
                name_key=name_key,
                blob_name=blob_name,
                current_version_id=version_id,
                parent_file_id=parent_file_id,
                comment_count=0,
                version=1,
                attributes={},
                uploaded_by_user_id=None,
                assignee_user_id=None,
                expires_at=expires_at,
                last_run_id=None,
                deleted_at=None,
                deleted_by_user_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            insert(file_versions).values(
                id=version_id,
                file_id=file_id,
                version_no=1,
                origin=origin,
                run_id=None,
                created_by_user_id=None,
                sha256="demo-sha",
                byte_size=10,
                content_type=content_type,
                filename_at_upload=name,
                blob_version_id="v1",
                created_at=now,
                updated_at=now,
            )
        )

    return file_id, version_id
