from __future__ import annotations

from __future__ import annotations

from pathlib import Path

from ade_engine.__main__ import main

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "templates" / "config-packages" / "default" / "src" / "ade_config" / "manifest.json"


def test_main_version_flag(capsys) -> None:
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "ade-engine" in captured.out


def test_main_prints_manifest(capsys) -> None:
    code = main(["--manifest-path", str(MANIFEST_PATH)])
    captured = capsys.readouterr()

    assert code == 0
    assert '"config_manifest"' in captured.out
