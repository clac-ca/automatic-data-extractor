"""Console entrypoint for ``python -m ade_engine``."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from ade_engine import (
    DEFAULT_METADATA,
    ManifestNotFoundError,
    TelemetryConfig,
    load_config_manifest,
    run_job,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ade_engine",
        description="ADE engine module entrypoint.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the ade_engine version and exit.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Optional path to an ade_config manifest (defaults to the installed package resource).",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        help="Run the worker pipeline for the specified job.",
    )
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        help="Root directory containing per-job folders (defaults to ADE_JOBS_DIR/ADE_DATA_DIR).",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Run without sandboxing (used by integration tests).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 when the module entrypoint completes successfully."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.version and not args.job_id:
        print(f"{DEFAULT_METADATA.name} {DEFAULT_METADATA.version}")
        return 0

    if args.job_id:
        telemetry = TelemetryConfig(
            correlation_id=os.environ.get("ADE_TELEMETRY_CORRELATION_ID")
        )
        result = run_job(
            args.job_id,
            jobs_dir=args.jobs_dir,
            manifest_path=args.manifest_path,
            safe_mode=args.safe_mode,
            telemetry=telemetry,
        )
        payload = {
            "engine_version": DEFAULT_METADATA.version,
            "job": {
                "job_id": result.job_id,
                "status": result.status,
                "outputs": [str(path) for path in result.output_paths],
                "artifact": str(result.artifact_path),
                "events": str(result.events_path),
            },
        }
        if result.error:
            payload["job"]["error"] = result.error
        print(json.dumps(payload, indent=2))
        return 0 if result.status == "succeeded" else 1

    try:
        manifest = load_config_manifest(manifest_path=args.manifest_path)
    except ManifestNotFoundError as exc:
        print(f"Manifest error: {exc}")
        return 1
    print(
        json.dumps(
            {
                "engine_version": DEFAULT_METADATA.version,
                "config_manifest": manifest,
            },
            indent=2,
        )
    )
    return 0


def console_entrypoint() -> NoReturn:
    """Console script helper for the module entrypoint."""

    raise SystemExit(main())
