#!/usr/bin/env python3
"""
Build a proof-of-concept ADE runtime environment.

This mirrors the steps described in docs/developers/02-build-venv.md:

1. Create a dedicated virtual environment under ./data/poc/.venv/<config_id>.
2. Install the local ade_engine package + a config project (default template).
3. Optionally install additional config dependencies declared in pyproject.toml.
4. Verify imports via ``python -I -B -c "import ade_engine, ade_config"``.

Run from the repository root:

    python scripts/build_venv_poc.py --workspace demo --config demo-config
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = REPO_ROOT / "apps" / "api" / "app" / "templates" / "config_packages" / "default"
LOCAL_ENGINE = REPO_ROOT / "packages" / "ade-engine"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a POC ADE virtual environment.")
    parser.add_argument(
        "--workspace",
        default="demo-workspace",
        help="Workspace identifier used for folder layout.",
    )
    parser.add_argument(
        "--config",
        default="demo-config",
        help="Config identifier used for folder layout.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=TEMPLATE_CONFIG,
        help="Path to the ade_config project to install (defaults to the bundled template).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=REPO_ROOT / "data" / "poc",
        help="Root directory for generated workspaces/venvs/cache.",
    )
    return parser.parse_args()


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    args = parse_args()

    venv_dir = args.data_root / ".venv" / args.workspace / args.config
    pip_cache_dir = args.data_root / "cache" / "pip"

    pip_cache_dir.mkdir(parents=True, exist_ok=True)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    if not venv_dir.exists():
        print(f"[venv] creating {venv_dir}")
        run([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print(f"[venv] reusing existing {venv_dir}")

    python_bin = venv_python(venv_dir)
    pip_env = os.environ.copy()
    pip_env["PIP_CACHE_DIR"] = str(pip_cache_dir)

    run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "wheel"], env=pip_env)
    run([str(python_bin), "-m", "pip", "install", str(LOCAL_ENGINE)], env=pip_env)
    run([str(python_bin), "-m", "pip", "install", str(args.config_path.resolve())], env=pip_env)

    run(
        [
            str(python_bin),
            "-I",
            "-B",
            "-c",
            'import ade_engine, ade_config; print("import ok:", ade_engine.__version__)',
        ]
    )

    print(f"[done] venv ready at {venv_dir}")


if __name__ == "__main__":
    main()
