#!/usr/bin/env python3
"""
Build a proof-of-concept ADE runtime environment using the backend builder.

This script is a thin CLI wrapper around ``apps.api.app.features.builds.builder``
so the local workflow matches backend behavior (metadata, layout, pip flags).
Storage paths default to ``ADE_VENVS_DIR``/``ADE_PIP_CACHE_DIR`` (falling back to
the repo's ./data layout) so you can share caches with the API service.

Run from the repository root:

    python scripts/build_venv_poc.py --workspace demo --config demo-config
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from apps.api.app.features.builds.builder import VirtualEnvironmentBuilder
from apps.api.app.features.builds.exceptions import BuildExecutionError
from apps.api.app.settings import DEFAULT_PIP_CACHE_DIR, DEFAULT_VENVS_DIR

TEMPLATE_CONFIG = REPO_ROOT / "apps" / "api" / "app" / "templates" / "config_packages" / "default"
LOCAL_ENGINE = REPO_ROOT / "packages" / "ade-engine"
DEFAULT_TIMEOUT = 600.0
ENV_VENVS_DIR = "ADE_VENVS_DIR"
ENV_PIP_CACHE_DIR = "ADE_PIP_CACHE_DIR"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a POC ADE virtual environment.")
    parser.add_argument(
        "--workspace",
        default="poc-workspace",
        help="Workspace identifier used for folder layout.",
    )
    parser.add_argument(
        "--config",
        default="poc-config",
        help="Config identifier used for folder layout.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=TEMPLATE_CONFIG,
        help="Path to the ade_config project to install (defaults to the bundled template).",
    )
    parser.add_argument(
        "--build-id",
        help="Optional build identifier appended to the venv directory.",
    )
    parser.add_argument(
        "--engine-spec",
        default=str(LOCAL_ENGINE),
        help="pip spec to install for ade_engine (defaults to local path).",
    )
    parser.add_argument(
        "--python-bin",
        help="Python interpreter to invoke `python -m venv` (defaults to sys.executable).",
    )
    parser.add_argument(
        "--pip-cache-dir",
        type=Path,
        help="Directory for pip's download cache (defaults to ADE_PIP_CACHE_DIR).",
    )
    parser.add_argument(
        "--venvs-dir",
        type=Path,
        help="Directory that stores ADE virtual environments (defaults to ADE_VENVS_DIR).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-command timeout (seconds) for the builder subprocess calls.",
    )
    parser.add_argument(
        "--stream-logs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stream subprocess stdout/stderr directly to this console (default: on).",
    )
    return parser.parse_args()


def _normalize_path(value: Path | str) -> Path:
    return Path(value).expanduser().resolve()


def _resolve_path(arg_value: Path | None, *, env_name: str, default: Path) -> Path:
    if arg_value is not None:
        return _normalize_path(arg_value)
    env_value = os.environ.get(env_name)
    if env_value:
        return _normalize_path(env_value)
    default_value = Path(default)
    if not default_value.is_absolute():
        default_value = REPO_ROOT / default_value
    return _normalize_path(default_value)


async def run_builder(args: argparse.Namespace) -> None:
    build_id = args.build_id or f"poc-{uuid4().hex[:8]}"
    config_path = args.config_path.resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config project not found: {config_path}")

    venvs_root = _resolve_path(args.venvs_dir, env_name=ENV_VENVS_DIR, default=DEFAULT_VENVS_DIR)
    pip_cache_dir = _resolve_path(
        args.pip_cache_dir,
        env_name=ENV_PIP_CACHE_DIR,
        default=DEFAULT_PIP_CACHE_DIR,
    )
    pip_cache_dir.mkdir(parents=True, exist_ok=True)

    builder = VirtualEnvironmentBuilder()
    target_path = (venvs_root / args.workspace / args.config / build_id).resolve()
    python_bin = args.python_bin

    print(f"[build] workspace={args.workspace} config={args.config} build_id={build_id}")
    print(f"[paths] venvs_root={venvs_root}")
    print(f"[paths] target={target_path}")
    print(f"[config] config_path={config_path}")
    print(f"[engine] spec={args.engine_spec}")
    print(f"[pip] cache_dir={pip_cache_dir}")

    artifacts = await builder.build(
        build_id=build_id,
        workspace_id=args.workspace,
        config_id=args.config,
        target_path=target_path,
        config_path=config_path,
        engine_spec=args.engine_spec,
        pip_cache_dir=pip_cache_dir,
        python_bin=python_bin,
        timeout=args.timeout,
        stream_output=args.stream_logs,
    )

    print(
        "[result] venv ready at {path} (python={py}, engine={engine})".format(
            path=target_path,
            py=artifacts.python_version,
            engine=artifacts.engine_version,
        )
    )


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run_builder(args))
    except BuildExecutionError as exc:
        print(f"[error] build failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
