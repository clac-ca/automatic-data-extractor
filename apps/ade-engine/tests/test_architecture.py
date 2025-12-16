from __future__ import annotations

import subprocess
from pathlib import Path


def test_import_layers() -> None:
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["lint-imports", "--config", str(root / ".importlinter")], cwd=root, check=True)
