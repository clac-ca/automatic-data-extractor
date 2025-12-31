from pathlib import Path

import pytest

from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunExecutionResult
from ade_api.infra.storage import workspace_config_root

from tests.unit.features.runs.helpers import build_runs_service


@pytest.mark.asyncio()
async def test_execute_engine_sets_config_package_flag(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, configuration, document, _fake_builds, settings = await build_runs_service(
        session,
        tmp_path,
    )
    options = RunCreateOptions(input_document_id=str(document.id))
    run = await service.prepare_run(configuration_id=configuration.id, options=options)
    await service._ensure_run_build(run=run, options=options)
    context = await service._execution_context_for_run(run.id)

    captured_command: list[str] | None = None

    class FakeRunner:
        def __init__(self, *, command, env) -> None:  # noqa: ARG002
            nonlocal captured_command
            captured_command = command
            self.returncode = 0

        async def stream(self):
            if False:  # pragma: no cover
                yield None

    monkeypatch.setattr("ade_api.features.runs.service.EngineSubprocessRunner", FakeRunner)

    frames = [
        frame
        async for frame in service._execute_engine(
            run=run,
            context=context,
            options=options,
            safe_mode_enabled=False,
        )
    ]

    assert captured_command is not None
    assert "--config-package" in captured_command
    idx = captured_command.index("--config-package")
    expected = workspace_config_root(settings, configuration.workspace_id, configuration.id)
    assert captured_command[idx + 1] == str(expected)
    assert any(isinstance(frame, RunExecutionResult) for frame in frames)
