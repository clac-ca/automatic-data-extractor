from pathlib import Path

from typer.testing import CliRunner

from ade_engine import Engine
from ade_engine.main import app
from ade_engine.types.run import RunResult, RunStatus


runner = CliRunner()


def test_run_command_happy_path(tmp_path, monkeypatch):
    input_file = tmp_path / "input.xlsx"
    input_file.write_text("dummy")

    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    calls: dict[str, Path] = {}

    def fake_run(self, request, logger=None, events=None, **_kwargs):
        calls["input"] = Path(request.input_file)
        calls["output"] = Path(request.output_file)
        calls["logs_file"] = Path(request.logs_file)
        output_path = Path(request.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok")
        return RunResult(
            status=RunStatus.SUCCEEDED,
            error=None,
            output_path=output_path,
            logs_dir=Path(request.logs_dir or request.output_dir or "."),
            processed_file=request.input_file.name,
        )

    monkeypatch.setattr(Engine, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "run",
            "--input",
            str(input_file),
            "--config-package",
            "data/templates/config_packages/default",
            "--output-dir",
            str(output_dir),
            "--logs-dir",
            str(logs_dir),
        ],
    )

    assert result.exit_code == 0
    assert "succeeded" in result.stdout
    assert calls["input"] == input_file.resolve()
    assert calls["output"].parent == output_dir.resolve()
    assert calls["logs_file"].parent == logs_dir.resolve()


def test_run_command_missing_config(tmp_path):
    input_file = tmp_path / "input.csv"
    input_file.write_text("a,b\n1,2\n")

    result = runner.invoke(
        app,
        [
            "run",
            "--input",
            str(input_file),
            "--config-package",
            "does.not.exist",
            "--output-dir",
            str(tmp_path / "output"),
            "--logs-dir",
            str(tmp_path / "logs"),
        ],
    )

    assert result.exit_code == 1
    assert "config_error" in result.stdout
