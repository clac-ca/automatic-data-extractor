"""Build ade.run_summary/v1 objects from telemetry events."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from ade_engine.schemas import AdeEvent, ManifestV1, RunSummaryV1
from pydantic import ValidationError

TableKey = tuple[str, str | None, int]


def _table_key(source_file: str, source_sheet: str | None, table_index: int) -> TableKey:
    return (source_file, source_sheet, table_index)


def _sum_if_complete(keys: list[TableKey], counts: dict[TableKey, int]) -> int | None:
    if not keys:
        return 0
    total = 0
    for key in keys:
        if key not in counts:
            return None
        total += counts[key]
    return total


def build_run_summary(
    *,
    events: Iterable[AdeEvent],
    manifest: ManifestV1 | None,
    workspace_id: str | None,
    configuration_id: str | None,
    configuration_version: str | None,
    run_id: str,
    env_reason: str | None = None,
    env_reused: bool | None = None,
) -> RunSummaryV1:
    """Aggregate a RunSummaryV1 from telemetry events and manifest metadata."""

    events_list = list(events)
    table_keys: list[TableKey] = []
    table_row_counts: dict[TableKey, int] = {}
    input_files: set[str] = set()
    input_sheets: set[tuple[str, str | None]] = set()
    mapped_fields: set[str] = set()
    mapped_scores: dict[str, float] = {}
    validation_issue_count_total = 0
    issue_counts_by_severity: defaultdict[str, int] = defaultdict(int)
    issue_counts_by_code: defaultdict[str, int] = defaultdict(int)
    unmapped_column_total = 0
    file_issue_counts: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    file_issue_codes: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    file_issue_totals: defaultdict[str, int] = defaultdict(int)
    field_issue_counts: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    field_issue_codes: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    field_issue_totals: defaultdict[str, int] = defaultdict(int)
    file_tables: defaultdict[str, list[TableKey]] = defaultdict(list)

    started_event: AdeEvent | None = None
    completed_event: AdeEvent | None = None

    for event in events_list:
        payload = event.model_extra or {}
        if event.type == "run.started":
            started_event = started_event or event
        elif event.type == "run.completed":
            completed_event = event

        if event.type != "run.table.summary":
            continue

        table = payload
        if not isinstance(table, dict):
            continue

        try:
            key = _table_key(
                str(table["source_file"]),
                table.get("source_sheet"),
                int(table["table_index"]),
            )
        except (KeyError, TypeError, ValueError):
            continue

        table_keys.append(key)
        source_file = str(table["source_file"])
        source_sheet = table.get("source_sheet")
        input_files.add(source_file)
        input_sheets.add((source_file, source_sheet))
        file_tables[source_file].append(key)

        row_count = table.get("row_count")
        if isinstance(row_count, int):
            table_row_counts[key] = row_count

        unmapped_count = table.get("unmapped_column_count")
        if isinstance(unmapped_count, int):
            unmapped_column_total += unmapped_count

        mapped_fields_payload = table.get("mapped_fields") or []
        for mapped in mapped_fields_payload:
            if isinstance(mapped, str):
                field_name = mapped
                score = None
            elif isinstance(mapped, dict):
                field_name = mapped.get("field")
                score = mapped.get("score")
            else:
                continue
            if isinstance(field_name, str):
                mapped_fields.add(field_name)
                if isinstance(score, (int, float)):
                    mapped_scores[field_name] = max(mapped_scores.get(field_name, float("-inf")), float(score))

        validation = table.get("validation") or {}
        total = validation.get("total")
        if isinstance(total, int):
            validation_issue_count_total += total
            file_issue_totals[source_file] += total

        by_severity = validation.get("by_severity") or {}
        for severity, count in by_severity.items():
            if not isinstance(count, int):
                continue
            issue_counts_by_severity[str(severity)] += count
            file_issue_counts[source_file][str(severity)] += count

        by_code = validation.get("by_code") or {}
        for code, count in by_code.items():
            if not isinstance(count, int):
                continue
            issue_counts_by_code[str(code)] += count
            file_issue_codes[source_file][str(code)] += count

        by_field = validation.get("by_field") or {}
        for field_name, details in by_field.items():
            if not isinstance(details, dict):
                continue
            total_for_field = details.get("total")
            if isinstance(total_for_field, int):
                field_issue_totals[str(field_name)] += total_for_field
            field_severity = details.get("by_severity") or {}
            for severity, count in field_severity.items():
                if not isinstance(count, int):
                    continue
                field_issue_counts[str(field_name)][str(severity)] += count
            field_codes = details.get("by_code") or {}
            for code, count in field_codes.items():
                if not isinstance(count, int):
                    continue
                field_issue_codes[str(field_name)][str(code)] += count

    canonical_fields: dict[str, tuple[str | None, bool]] = {}
    if manifest:
        for name, field in manifest.columns.fields.items():
            canonical_fields[name] = (field.label, field.required)
    else:
        seen_fields = set(mapped_fields) | set(field_issue_totals.keys())
        canonical_fields = {field: (None, False) for field in seen_fields}

    declared_fields = len(canonical_fields)
    required_fields = len([name for name, (_, required) in canonical_fields.items() if required])
    mapped_field_count = (
        len([f for f in canonical_fields if f in mapped_fields])
        if canonical_fields
        else len(mapped_fields)
    )

    start_timestamp = started_event.created_at if started_event else None
    completed_timestamp = completed_event.created_at if completed_event else None
    duration_seconds = (
        (completed_timestamp - start_timestamp).total_seconds()
        if completed_timestamp and start_timestamp
        else None
    )

    completion_payload = completed_event.model_extra or {} if completed_event else {}
    completion_error = (
        completed_event.error
        if completed_event and completed_event.error is not None
        else completion_payload.get("error") if isinstance(completion_payload, dict) else None
    )
    status_literal = None
    if isinstance(completion_payload, dict):
        status_literal = (
            completion_payload.get("status")
            or completion_payload.get("engine_status")
        )
    summary_run_status = status_literal or ("succeeded" if completed_event else "failed")

    by_file = []
    for source_file in sorted(file_tables.keys() or input_files):
        keys_for_file = file_tables[source_file]
        row_count = _sum_if_complete(keys_for_file, table_row_counts)
        by_file.append(
            {
                "source_file": source_file,
                "table_count": len(keys_for_file),
                "row_count": row_count,
                "validation_issue_count_total": file_issue_totals[source_file],
                "issue_counts_by_severity": dict(file_issue_counts[source_file]),
                "issue_counts_by_code": dict(file_issue_codes[source_file]),
            }
        )

    if not by_file and input_files:
        for source_file in sorted(input_files):
            by_file.append(
                {
                    "source_file": source_file,
                    "table_count": 0,
                    "row_count": None,
                    "validation_issue_count_total": 0,
                    "issue_counts_by_severity": {},
                    "issue_counts_by_code": {},
                }
            )

    field_names = (
        list(manifest.columns.order) if manifest else sorted(canonical_fields.keys())
    )
    extra_fields = [f for f in canonical_fields.keys() if f not in field_names]
    field_names.extend(sorted(extra_fields))

    by_field = []
    for field in field_names:
        label, required = canonical_fields.get(field, (None, False))
        issue_total = field_issue_totals.get(field, 0)
        by_field.append(
            {
                "field": field,
                "label": label,
                "required": required,
                "mapped": field in mapped_fields,
                "max_score": mapped_scores.get(field),
                "validation_issue_count_total": issue_total,
                "issue_counts_by_severity": dict(field_issue_counts.get(field, {})),
                "issue_counts_by_code": dict(field_issue_codes.get(field, {})),
            }
        )

    summary_run = {
        "id": run_id,
        "workspace_id": workspace_id,
        "configuration_id": configuration_id,
        "configuration_version": configuration_version,
        "status": summary_run_status,
        "failure_code": completion_error.get("code") if isinstance(completion_error, dict) else None,
        "failure_stage": completion_error.get("stage") if isinstance(completion_error, dict) else None,
        "failure_message": completion_error.get("message") if isinstance(completion_error, dict) else None,
        "engine_version": (started_event.model_extra or {}).get("engine_version") if started_event else None,  # type: ignore[union-attr]
        "config_version": manifest.version if manifest else None,  # type: ignore[union-attr]
        "env_reason": env_reason,
        "env_reused": env_reused,
        "started_at": start_timestamp or datetime.now(UTC),
        "completed_at": completed_timestamp,
        "duration_seconds": duration_seconds,
    }

    summary_core = {
        "input_file_count": len(input_files),
        "input_sheet_count": len(input_sheets),
        "table_count": len(table_keys),
        "row_count": _sum_if_complete(table_keys, table_row_counts),
        "canonical_field_count": declared_fields,
        "required_field_count": required_fields,
        "mapped_field_count": mapped_field_count,
        "unmapped_column_count": unmapped_column_total,
        "validation_issue_count_total": validation_issue_count_total,
        "issue_counts_by_severity": dict(issue_counts_by_severity),
        "issue_counts_by_code": dict(issue_counts_by_code),
    }

    return RunSummaryV1(
        run=summary_run,
        core=summary_core,
        breakdowns={"by_file": by_file, "by_field": by_field},
    )


def build_run_summary_from_paths(
    *,
    events_path: Path | None,
    manifest_path: Path | None,
    workspace_id: str | None,
    configuration_id: str | None,
    configuration_version: str | None,
    run_id: str,
    env_reason: str | None = None,
    env_reused: bool | None = None,
) -> RunSummaryV1:
    """Load events from disk and build a RunSummaryV1."""

    events: list[AdeEvent] = []
    if events_path and events_path.exists():
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                candidate = line.strip()
                if not candidate:
                    continue
                try:
                    events.append(AdeEvent.model_validate_json(candidate))
                except ValidationError:
                    continue

    manifest = None
    if manifest_path and manifest_path.exists():
        try:
            manifest = ManifestV1.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        except ValidationError:
            manifest = None

    return build_run_summary(
        events=events,
        manifest=manifest,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        configuration_version=configuration_version,
        run_id=run_id,
        env_reason=env_reason,
        env_reused=env_reused,
    )
