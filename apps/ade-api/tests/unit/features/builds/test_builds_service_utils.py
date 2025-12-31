import json
from datetime import UTC, datetime, timedelta

import pytest

from ade_api.common.time import utc_now
from ade_api.db.mixins import generate_uuid7
from ade_api.infra.storage import build_venv_root
from ade_api.models import Build, BuildStatus

from tests.unit.features.builds.helpers import FakeBuilder, TrackingBuilder, create_configuration


@pytest.mark.asyncio()
async def test_is_stale_handles_naive_datetimes(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))

    fixed_now = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    service._now = lambda: fixed_now  # type: ignore[assignment]

    timeout = service.settings.build_timeout

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.BUILDING,
        fingerprint="fingerprint",
        created_at=fixed_now,
        started_at=(fixed_now - timedelta(seconds=timeout + 1)).replace(tzinfo=None),
    )
    assert service._is_stale(build) is True

    build.started_at = (fixed_now - timedelta(seconds=timeout - 1)).replace(tzinfo=None)
    assert service._is_stale(build) is False

    build.status = BuildStatus.QUEUED
    assert service._is_stale(build) is False


@pytest.mark.asyncio()
async def test_ensure_local_env_uses_marker_when_ids_are_strings(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    builder = TrackingBuilder()
    service = service_factory(session, builder=builder)

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        fingerprint="fp-123",
        engine_spec="demo",
        engine_version="0.0.1",
        python_version="3.11.0",
    )
    session.add(build)
    await session.commit()

    venv_root = build_venv_root(service.settings, workspace.id, configuration.id, build.id)
    marker_path = venv_root / ".venv" / "ade_build.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_payload = {
        "build_id": str(build.id),
        "fingerprint": build.fingerprint,
        "engine_version": build.engine_version,
    }
    marker_path.write_text(json.dumps(marker_payload), encoding="utf-8")

    resolved = await service.ensure_local_env(build=build)

    assert resolved == marker_path.parent
    assert builder.invocations == 0
