from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from ade_api.common.time import utc_now
from ade_api.common.ids import generate_uuid7
from ade_db.models import (
    Configuration,
    ConfigurationStatus,
    File,
    FileKind,
    FileVersion,
    FileVersionOrigin,
    Run,
    RunStatus,
)
from tests.api.utils import login


async def auth_headers(client: AsyncClient, account) -> dict[str, str]:
    token, _ = await login(client, email=account.email, password=account.password)
    return {"X-API-Key": token}


def make_configuration(
    *,
    workspace_id: UUID,
    name: str,
    status: ConfigurationStatus = ConfigurationStatus.ACTIVE,
) -> Configuration:
    return Configuration(
        workspace_id=workspace_id,
        display_name=name,
        status=status,
    )


def make_document(
    *,
    workspace_id: UUID,
    filename: str,
    byte_size: int = 12,
) -> File:
    file_id = generate_uuid7()
    version_id = generate_uuid7()
    name_key = filename.casefold()
    document = File(
        id=file_id,
        workspace_id=workspace_id,
        kind=FileKind.INPUT,
        name=filename,
        name_key=name_key,
        blob_name=f"{workspace_id}/files/{file_id}",
        attributes={},
        uploaded_by_user_id=None,
        comment_count=0,
    )
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=None,
        sha256="deadbeef",
        byte_size=byte_size,
        content_type="text/csv",
        filename_at_upload=filename,
        storage_version_id="v1",
    )
    document.current_version = version
    document.versions = [version]
    return document


def make_run(
    *,
    workspace_id: UUID,
    configuration_id: UUID,
    file_version_id: UUID,
    status: RunStatus,
    deps_digest: str = "sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d",
) -> Run:
    return Run(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        input_file_version_id=file_version_id,
        deps_digest=deps_digest,
        status=status,
        created_at=utc_now(),
    )
