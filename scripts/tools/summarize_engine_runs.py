#!/usr/bin/env python
"""
Summarize engine NDJSON logs for quick coverage checks.

Usage:
    python scripts/summarize_engine_runs.py /tmp/ade-logs --out data/samples/output/detector-pass2/coverage.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_latest_run_summary(log_path: Path) -> Optional[Tuple[dict, str]]:
    """Return the most recent engine.run.summary payload found in the log."""
    latest_created_at: Optional[str] = None
    latest_payload: Optional[dict] = None

    try:
        with log_path.open() as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "engine.run.summary":
                    continue

                created_at = event.get("created_at")
                payload = event.get("payload")
                if payload is None:
                    continue

                if latest_created_at is None or (created_at and created_at > latest_created_at):
                    latest_created_at = created_at
                    latest_payload = payload
    except FileNotFoundError:
        return None

    if latest_payload is None or latest_created_at is None:
        return None

    return latest_payload, latest_created_at


def summarize_logs(logs_root: Path) -> dict:
    field_frequency: Dict[str, int] = defaultdict(int)
    unmapped_frequency: Dict[str, int] = defaultdict(int)
    missing_examples: Dict[str, List[str]] = defaultdict(list)
    latest_runs_by_file: Dict[str, dict] = {}

    for log_file in sorted(logs_root.rglob("engine_events.ndjson")):
        summary_data = load_latest_run_summary(log_file)
        if summary_data is None:
            continue

        summary, created_at = summary_data
        processed_file = (
            summary.get("details", {}).get("processed_file")
            or summary.get("source", {}).get("processed_file")
            or log_file.parent.name
        )
        fields = summary.get("fields", [])
        mapped_fields = [f["field"] for f in fields if f.get("mapped")]
        unmapped_fields = [f["field"] for f in fields if not f.get("mapped")]

        candidate = {
            "file": processed_file,
            "run_id": summary.get("source", {}).get("run_id"),
            "created_at": created_at,
            "mapped_fields": mapped_fields,
            "unmapped_fields": unmapped_fields,
            "counts": {
                "mapped": len(mapped_fields),
                "unmapped": len(unmapped_fields),
                "total": len(fields),
            },
        }

        existing = latest_runs_by_file.get(processed_file)
        if existing is None or created_at > existing["created_at"]:
            latest_runs_by_file[processed_file] = candidate

    runs: List[dict] = []
    for run in sorted(latest_runs_by_file.values(), key=lambda item: item["file"]):
        runs.append(run)
        for field in run["mapped_fields"]:
            field_frequency[field] += 1
        for field in run["unmapped_fields"]:
            unmapped_frequency[field] += 1
            if len(missing_examples[field]) < 5:
                missing_examples[field].append(run["file"])

    total_runs = len(runs)
    all_fields = set(field_frequency) | set(unmapped_frequency)
    low_coverage_fields = []
    for field in sorted(all_fields):
        mapped_count = field_frequency.get(field, 0)
        unmapped_count = unmapped_frequency.get(field, 0)
        coverage_rate = mapped_count / total_runs if total_runs else 0.0
        low_coverage_fields.append(
            {
                "field": field,
                "mapped_count": mapped_count,
                "unmapped_count": unmapped_count,
                "coverage_rate": round(coverage_rate, 3),
                "missing_examples": missing_examples.get(field, []),
            }
        )

    low_coverage_fields.sort(key=lambda item: (item["coverage_rate"], item["unmapped_count"] * -1, item["field"]))

    return {
        "logs_root": str(logs_root),
        "runs": sorted(runs, key=lambda run: run["file"]),
        "aggregate": {
            "totals": {"runs": total_runs},
            "field_frequency": dict(sorted(field_frequency.items())),
            "unmapped_frequency": dict(sorted(unmapped_frequency.items())),
            "low_coverage_fields": low_coverage_fields,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize engine NDJSON logs for mapping coverage.")
    parser.add_argument("logs_root", type=Path, help="Directory containing per-run engine_events.ndjson files.")
    parser.add_argument("--out", type=Path, help="Optional output file for JSON summary.")
    args = parser.parse_args()

    if not args.logs_root.exists():
        parser.error(f"logs_root does not exist: {args.logs_root}")

    summary = summarize_logs(args.logs_root)
    output = json.dumps(summary, indent=2)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
