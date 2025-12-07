"""Column mapping for extracted tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ade_engine.config.loader import ConfigRuntime
from ade_engine.core.errors import ConfigError
from ade_engine.types.contexts import RunContext
from ade_engine.types.mapping import ColumnMappingPatch
from ade_engine.types.tables import (
    ColumnMapping,
    ExtractedTable,
    MappedField,
    MappedTable,
    PassthroughField,
)

MAPPING_SCORE_THRESHOLD = 0.5
COLUMN_SAMPLE_SIZE = 10
DEFAULT_REUSABLE_FIELDS: set[str] = {"state_prov_code", "postal_code"}


class _NullEventEmitter:
    def custom(self, *_args, **_kwargs):
        return None

    def config_emitter(self):
        return self


@dataclass
class _ColumnCandidate:
    index: int
    header: str
    values: list[Any]


def _collect_candidates(extracted: ExtractedTable) -> list[_ColumnCandidate]:
    width = len(extracted.header)
    for row in extracted.rows:
        width = max(width, len(row))

    candidates: list[_ColumnCandidate] = []
    for idx in range(width):
        header = extracted.header[idx] if idx < len(extracted.header) else ""
        values = [row[idx] if idx < len(row) else None for row in extracted.rows]
        candidates.append(_ColumnCandidate(index=idx, header=header, values=values))
    return candidates


def _normalize_detector_scores(result: Any, *, default_field: str) -> Mapping[str, float]:
    if isinstance(result, Mapping):
        scores_map = result.get("scores", result)
        normalized: dict[str, float] = {}
        for field, delta in scores_map.items():
            try:
                normalized[str(field)] = float(delta)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"Detector returned a non-numeric score for field {field!r}: {delta!r}") from exc
        return normalized

    try:
        delta = float(result) if result is not None else 0.0
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Detector returned a non-numeric score: {result!r}") from exc
    return {default_field: delta}


def _project_rows(mapping: ColumnMapping, extracted: ExtractedTable) -> list[list[Any]]:
    projected: list[list[Any]] = []
    for row in extracted.rows:
        canonical_values = [
            row[field.source_col] if field.source_col is not None and field.source_col < len(row) else None
            for field in mapping.fields
        ]
        passthrough_values = [
            row[p.source_col] if p.source_col < len(row) else None
            for p in mapping.passthrough
        ]
        projected.append(canonical_values + passthrough_values)
    return projected


class ColumnMapper:
    """Compute column mappings using manifest detectors."""

    def __init__(
        self,
        *,
        threshold: float = MAPPING_SCORE_THRESHOLD,
        sample_size: int = COLUMN_SAMPLE_SIZE,
        reusable_fields: set[str] | None = None,
    ) -> None:
        self.threshold = threshold
        self.sample_size = sample_size
        self.reusable_fields = reusable_fields or set(DEFAULT_REUSABLE_FIELDS)

    def map(
        self,
        extracted: ExtractedTable,
        runtime: ConfigRuntime,
        run_ctx: RunContext,
        *,
        logger=None,
    ) -> MappedTable:
        emitter = _NullEventEmitter()

        candidates = _collect_candidates(extracted)
        field_scores: dict[str, dict[int, float]] = {}

        state: dict[str, Any] = {}

        for field_name, module in runtime.columns.items():
            for candidate in candidates:
                for detector in module.detectors:
                    result = detector(
                        run=run_ctx,
                        state=state,
                        extracted_table=extracted,
                        raw_table=extracted,
                        unmapped_table=extracted,
                        input_file_name=extracted.origin.source_path.name,
                        file_name=extracted.origin.source_path.name,
                        column_index=candidate.index + 1,
                        header=candidate.header,
                        column_values=candidate.values,
                        column_values_sample=candidate.values[: self.sample_size],
                        manifest=runtime.manifest,
                        logger=logger,
                        event_emitter=emitter,
                    )
                    scores = _normalize_detector_scores(result, default_field=field_name)
                    for target_field, delta in scores.items():
                        if target_field not in runtime.manifest.columns.fields:
                            continue
                        bucket = field_scores.setdefault(target_field, {})
                        bucket[candidate.index] = bucket.get(candidate.index, 0.0) + delta

        used_columns: set[int] = set()
        mapped_fields: list[MappedField] = []
        for field in runtime.manifest.columns.order:
            scores_for_field = field_scores.get(field, {})
            best_candidate: _ColumnCandidate | None = None
            best_score: float | None = None
            allow_reuse = field in self.reusable_fields
            for candidate in candidates:
                if not allow_reuse and candidate.index in used_columns:
                    continue
                score = scores_for_field.get(candidate.index, 0.0)
                if score < self.threshold:
                    continue
                if best_score is None or score > best_score or (score == best_score and best_candidate and candidate.index < best_candidate.index):
                    best_candidate = candidate
                    best_score = score

            if best_candidate and best_score is not None:
                mapped_fields.append(
                    MappedField(
                        field=field,
                        source_col=best_candidate.index,
                        source_header=best_candidate.header,
                        score=best_score,
                    )
                )
                if not allow_reuse:
                    used_columns.add(best_candidate.index)
            else:
                mapped_fields.append(MappedField(field=field, source_col=None, source_header=None, score=None))

        passthrough: list[PassthroughField] = []
        if runtime.manifest.writer.append_unmapped_columns:
            for candidate in candidates:
                if candidate.index in used_columns:
                    continue
                passthrough.append(
                    PassthroughField(
                        source_col=candidate.index,
                        source_header=candidate.header,
                        output_name=f"{runtime.manifest.writer.unmapped_prefix}{candidate.index + 1}",
                    )
                )

        mapping = ColumnMapping(fields=mapped_fields, passthrough=passthrough)
        header = mapping.output_header
        rows = _project_rows(mapping, extracted)
        return MappedTable(
            origin=extracted.origin,
            region=extracted.region,
            mapping=mapping,
            extracted=extracted,
            header=header,
            rows=rows,
        )

    def apply_patch(
        self,
        mapped: MappedTable,
        patch: ColumnMappingPatch,
        manifest: Any,
    ) -> MappedTable:
        """Apply a ColumnMappingPatch to a mapped table."""

        if patch.assign:
            unknown = [field for field in patch.assign if field not in manifest.columns.order]
            if unknown:
                raise ConfigError(f"Patch assigns unknown field(s): {', '.join(unknown)}")

        max_index = len(mapped.extracted.header)
        if patch.assign:
            out_of_bounds = [idx for idx in patch.assign.values() if idx < 0 or idx >= max_index]
            if out_of_bounds:
                raise ConfigError(f"Patch assigns column index out of bounds: {out_of_bounds}")

        current_assignments: dict[str, int | None] = {mf.field: mf.source_col for mf in mapped.mapping.fields}
        new_assignments = dict(current_assignments)
        if patch.assign:
            new_assignments.update(patch.assign)

        claimed: dict[int, str] = {}
        for field, source_col in new_assignments.items():
            if source_col is None:
                continue
            if source_col in claimed:
                raise ConfigError(f"Patch maps multiple fields to column {source_col + 1}")
            claimed[source_col] = field

        passthrough: list[PassthroughField] = []
        requested_drop = patch.drop_passthrough or set()
        requested_rename = patch.rename_passthrough or {}

        existing_passthrough_cols = {p.source_col for p in mapped.mapping.passthrough}
        missing = [idx for idx in requested_drop if idx not in existing_passthrough_cols]
        if missing:
            raise ConfigError(f"Patch cannot drop non-passthrough columns: {missing}")

        rename_missing = [idx for idx in requested_rename if idx not in existing_passthrough_cols]
        if rename_missing:
            raise ConfigError(f"Patch cannot rename non-passthrough column(s): {rename_missing}")

        for p in mapped.mapping.passthrough:
            if p.source_col in requested_drop:
                continue
            output_name = requested_rename.get(p.source_col, p.output_name)
            passthrough.append(
                PassthroughField(
                    source_col=p.source_col,
                    source_header=p.source_header,
                    output_name=output_name,
                )
            )

        used_columns = set(col for col in new_assignments.values() if col is not None)
        passthrough = [p for p in passthrough if p.source_col not in used_columns]

        patched_fields: list[MappedField] = []
        for field in manifest.columns.order:
            source_col = new_assignments.get(field)
            if source_col is None:
                patched_fields.append(MappedField(field=field, source_col=None, source_header=None, score=None))
                continue

            header_value = mapped.extracted.header[source_col] if source_col < len(mapped.extracted.header) else ""
            patched_fields.append(
                MappedField(
                    field=field,
                    source_col=source_col,
                    source_header=header_value,
                    score=None,
                )
            )

        patched_mapping = ColumnMapping(fields=patched_fields, passthrough=passthrough)
        header = patched_mapping.output_header
        rows = _project_rows(patched_mapping, mapped.extracted)

        return MappedTable(
            origin=mapped.origin,
            region=mapped.region,
            mapping=patched_mapping,
            extracted=mapped.extracted,
            header=header,
            rows=rows,
        )


__all__ = ["ColumnMapper", "MAPPING_SCORE_THRESHOLD", "COLUMN_SAMPLE_SIZE", "DEFAULT_REUSABLE_FIELDS"]
