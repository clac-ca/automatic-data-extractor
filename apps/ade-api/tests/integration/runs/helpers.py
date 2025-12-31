from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from ade_api.common.time import utc_now
from ade_api.db.mixins import generate_uuid7
from ade_api.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    Run,
    RunStatus,
)
from tests.utils import login


async def auth_headers(client: AsyncClient, account) -> dict[str, str]:
    token, _ = await login(client, email=account.email, password=account.password)
    return {"Authorization": f"Bearer {token}"}


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


def make_build(
    *,
    workspace_id: UUID,
    configuration_id: UUID,
    status: BuildStatus = BuildStatus.READY,
    fingerprint: str = "fingerprint",
) -> Build:
    return Build(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        fingerprint=fingerprint,
        status=status,
        created_at=utc_now(),
    )


def make_document(
    *,
    workspace_id: UUID,
    filename: str,
    byte_size: int = 12,
) -> Document:
    stored_uri = f"documents/{filename}"
    return Document(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        original_filename=filename,
        content_type="text/csv",
        byte_size=byte_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )


def make_run(
    *,
    workspace_id: UUID,
    configuration_id: UUID,
    build_id: UUID,
    document_id: UUID,
    status: RunStatus,
) -> Run:
    return Run(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        build_id=build_id,
        input_document_id=document_id,
        status=status,
        created_at=utc_now(),
    )
