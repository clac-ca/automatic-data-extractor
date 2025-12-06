"""
Quick helper to summarize ADE engine run outputs using the emitted NDJSON events.

Usage (from repo root):
    python3 scripts/summarize_engine_runs.py data/samples/output

Outputs:
    - Per-file summary: mapped field count and list of mapped fields
    - Aggregate counts: how many files mapped each field
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def load_run_summary(events_path: Path) -> dict | None:
    """Return the last engine.run.summary event payload, if present."""
    summary = None
    with events_path.open() as f:
        for line in f:
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "engine.run.summary":
                summary = evt.get("payload")
    return summary


def summarize_runs(out_dir: Path) -> None:
    per_file: list[tuple[str, int, list[str]]] = []
    field_hits: Counter[str] = Counter()

    for events_path in sorted(out_dir.glob("*/engine_events.ndjson")):
        summary = load_run_summary(events_path)
        if not summary:
            continue
        fields = summary.get("fields", [])
        mapped = [f["field"] for f in fields if f.get("mapped")]
        per_file.append((events_path.parent.name, len(mapped), mapped))
        for field in mapped:
            field_hits[field] += 1

    if not per_file:
        print("No run summaries found.")
        return

    print("Per-file mapped field counts")
    for name, count, mapped in per_file:
        print(f"- {name}: {count} mapped → {', '.join(mapped) if mapped else 'none'}")

    print("\nAggregate mapping frequency (files mapped per field)")
    for field, count in field_hits.most_common():
        print(f"- {field}: {count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/summarize_engine_runs.py <logs_dir>")
        sys.exit(1)
    summarize_runs(Path(sys.argv[1]))
