import pytest

from ade_api.features.builds import service as builds_service_module

from tests.integration.builds.helpers import StubBuilder


@pytest.fixture(autouse=True)
def _override_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the builds service uses the stub builder in integration tests."""

    monkeypatch.setattr(builds_service_module, "VirtualEnvironmentBuilder", StubBuilder)
    StubBuilder.events = []
