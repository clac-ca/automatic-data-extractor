from __future__ import annotations

import pytest

from ade_api.features.configs.endpoints import configurations as configurations_endpoints


@pytest.fixture(autouse=True)
def _disable_validation_background_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid running build background jobs during configuration validation tests.

    The API schedules build validation tasks via `BackgroundTasks`, but these tests
    are focused on the configuration endpoints and should not execute venv/pip work.
    """

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(configurations_endpoints, "execute_build_background", _noop)

