"""Build ade.run_summary/v1 objects from artifacts and telemetry."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ade_engine.schemas import AdeEvent, ArtifactV1, ManifestV1, RunSummaryV1
from pydantic import ValidationError

TableKey = tuple[str, str | None, int]


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _status_value(value: object) -> str:
    return getattr(value, "value", None) or str(value)


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


def _extract_table_row_counts(events: Iterable[AdeEvent]) -> dict[TableKey, int]:
    counts: dict[TableKey, int] = {}
    for event in events:
        if event.type != "run.table.summary":
            continue
        table = (event.output_delta or {}).get("table") if event.output_delta else None
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
        row_count = table.get("row_count")
        if isinstance(row_count, int):
            counts[key] = row_count
    return counts


def build_run_summary(
    *,
    artifact: ArtifactV1,
    events: Iterable[AdeEvent] | None,
    manifest: ManifestV1 | None,
    workspace_id: str | None,
    configuration_id: str | None,
    configuration_version: str | None,
    run_id: str,
    env_reason: str | None = None,
    env_reused: bool | None = None,
) -> RunSummaryV1:
    """Aggregate a RunSummaryV1 from artifact + events + manifest metadata."""

    events_list = list(events or [])
    table_row_counts = _extract_table_row_counts(events_list)

    table_keys: list[TableKey] = []
    input_files: set[str] = set()
    input_sheets: set[tuple[str, str | None]] = set()
    mapped_fields: set[str] = set()
    mapped_scores: dict[str, float] = {}
    validation_issue_count_total = 0
    issue_counts_by_severity: defaultdict[str, int] = defaultdict(int)
    issue_counts_by_code: defaultdict[str, int] = defaultdict(int)
    file_issue_counts: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    file_issue_codes: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    file_issue_totals: defaultdict[str, int] = defaultdict(int)
    field_issue_counts: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    field_issue_codes: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    field_issue_totals: defaultdict[str, int] = defaultdict(int)
    file_tables: defaultdict[str, list[TableKey]] = defaultdict(list)

    for table in artifact.tables:
        key = _table_key(table.source_file, table.source_sheet, table.table_index)
        table_keys.append(key)
        input_files.add(table.source_file)
        input_sheets.add((table.source_file, table.source_sheet))
        file_tables[table.source_file].append(key)

        for mapped in table.mapped_columns:
            mapped_fields.add(mapped.field)
            mapped_scores[mapped.field] = max(mapped_scores.get(mapped.field, float("-inf")), mapped.score)

        for issue in table.validation_issues:
            validation_issue_count_total += 1
            issue_counts_by_severity[str(issue.severity)] += 1
            issue_counts_by_code[str(issue.code)] += 1
            file_issue_counts[table.source_file][str(issue.severity)] += 1
            file_issue_codes[table.source_file][str(issue.code)] += 1
            file_issue_totals[table.source_file] += 1
            field_issue_counts[str(issue.field)][str(issue.severity)] += 1
            field_issue_codes[str(issue.field)][str(issue.code)] += 1
            field_issue_totals[str(issue.field)] += 1

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

    summary_run_status = _status_value(getattr(artifact.run, "status", "succeeded"))
    error = getattr(artifact.run, "error", None)
    started_at = _parse_datetime(getattr(artifact.run, "started_at", None)) or datetime.now(timezone.utc)
    completed_at = _parse_datetime(getattr(artifact.run, "completed_at", None))
    duration_seconds = None
    if completed_at is not None and started_at:
        duration_seconds = (completed_at - started_at).total_seconds()

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
        # Handle cases where tables are missing but source files are known.
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
        "failure_code": getattr(error, "code", None),
        "failure_stage": getattr(error, "stage", None),
        "failure_message": getattr(error, "message", None),
        "engine_version": getattr(artifact.run, "engine_version", None),
        "config_version": getattr(artifact.config, "version", None),
        "env_reason": env_reason,
        "env_reused": env_reused,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration_seconds,
    }

    summary_core = {
        "input_file_count": len(input_files),
        "input_sheet_count": len(input_sheets),
        "table_count": len(artifact.tables),
        "row_count": _sum_if_complete(table_keys, table_row_counts),
        "canonical_field_count": declared_fields,
        "required_field_count": required_fields,
        "mapped_field_count": mapped_field_count,
        "unmapped_column_count": sum(len(table.unmapped_columns) for table in artifact.tables),
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
    artifact_path: Path,
    events_path: Path | None,
    manifest_path: Path | None,
    workspace_id: str | None,
    configuration_id: str | None,
    configuration_version: str | None,
    run_id: str,
    env_reason: str | None = None,
    env_reused: bool | None = None,
) -> RunSummaryV1:
    """Load artifacts/events from disk and build a RunSummaryV1."""

    artifact = ArtifactV1.model_validate_json(artifact_path.read_text(encoding="utf-8"))

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
        artifact=artifact,
        events=events,
        manifest=manifest,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        configuration_version=configuration_version,
        run_id=run_id,
        env_reason=env_reason,
        env_reused=env_reused,
    )
