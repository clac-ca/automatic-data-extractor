"""Column mapping for extracted tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ade_engine.config.loader import ConfigRuntime
from ade_engine.exceptions import ConfigError
from ade_engine.runtime import PluginInvoker
from ade_engine.types.contexts import RunContext
from ade_engine.types.mapping import ColumnMappingPatch
from ade_engine.types.tables import ColumnMapping, ExtractedTable, MappedField, MappedTable, PassthroughField

MAPPING_SCORE_THRESHOLD = 0.5
COLUMN_SAMPLE_SIZE = 10
DEFAULT_REUSABLE_FIELDS: set[str] = {"state_prov_code", "postal_code"}


@dataclass(frozen=True)
class _ColumnCandidate:
    index: int
    header: str
    values: list[Any]


def _collect_candidates(extracted: ExtractedTable) -> list[_ColumnCandidate]:
    width = max(len(extracted.header), max((len(row) for row in extracted.rows), default=0))

    candidates: list[_ColumnCandidate] = []
    for idx in range(width):
        header = extracted.header[idx] if idx < len(extracted.header) else ""
        values = [row[idx] if idx < len(row) else None for row in extracted.rows]
        candidates.append(_ColumnCandidate(index=idx, header=header, values=values))
    return candidates


def _normalize_detector_scores(result: Any, *, default_field: str) -> Mapping[str, float]:
    if isinstance(result, Mapping):
        scores = result.get("scores", result)
        normalized: dict[str, float] = {}
        for field, delta in scores.items():
            try:
                normalized[str(field)] = float(delta)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"Detector returned a non-numeric score for field {field!r}: {delta!r}") from exc
        return normalized

    if result is None:
        return {default_field: 0.0}

    try:
        return {default_field: float(result)}
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Detector returned a non-numeric score: {result!r}") from exc


def _project_rows(mapping: ColumnMapping, extracted: ExtractedTable) -> list[list[Any]]:
    projected: list[list[Any]] = []
    for row in extracted.rows:
        canonical_values = [
            row[field.source_col] if field.source_col is not None and field.source_col < len(row) else None
            for field in mapping.fields
        ]
        passthrough_values = [row[p.source_col] if p.source_col < len(row) else None for p in mapping.passthrough]
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
        self.reusable_fields = set(reusable_fields or DEFAULT_REUSABLE_FIELDS)

    def map(
        self,
        extracted: ExtractedTable,
        runtime: ConfigRuntime,
        run_ctx: RunContext,  # noqa: ARG002 - available via invoker.base_kwargs()
        *,
        invoker: PluginInvoker,
        logger=None,  # noqa: ARG002 - included for config callables
    ) -> MappedTable:
        candidates = _collect_candidates(extracted)
        manifest_fields = set(runtime.manifest.column_names)

        # field -> candidate_index -> score
        field_scores: dict[str, dict[int, float]] = {}

        for default_field, module in runtime.columns.items():
            for candidate in candidates:
                for detector in module.detectors:
                    result = invoker.call(
                        detector,
                        extracted_table=extracted,
                        raw_table=extracted,  # legacy alias
                        unmapped_table=extracted,  # legacy alias
                        column_index=candidate.index + 1,  # legacy 1-based
                        header=candidate.header,
                        column_values=candidate.values,
                        column_values_sample=candidate.values[: self.sample_size],
                    )

                    for target_field, delta in _normalize_detector_scores(result, default_field=default_field).items():
                        if target_field not in manifest_fields:
                            continue
                        scores = field_scores.setdefault(target_field, {})
                        scores[candidate.index] = scores.get(candidate.index, 0.0) + delta

        used_columns: set[int] = set()
        mapped_fields: list[MappedField] = []

        for field in runtime.manifest.column_names:
            allow_reuse = field in self.reusable_fields
            scores_for_field = field_scores.get(field, {})

            eligible = [
                (candidate, scores_for_field.get(candidate.index, 0.0))
                for candidate in candidates
                if (allow_reuse or candidate.index not in used_columns)
                and scores_for_field.get(candidate.index, 0.0) >= self.threshold
            ]

            if eligible:
                best_candidate, best_score = max(eligible, key=lambda item: (item[1], -item[0].index))
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
        return MappedTable(
            origin=extracted.origin,
            region=extracted.region,
            mapping=mapping,
            extracted=extracted,
            header=mapping.output_header,
            rows=_project_rows(mapping, extracted),
        )

    def apply_patch(self, mapped: MappedTable, patch: ColumnMappingPatch, manifest: Any) -> MappedTable:
        """Apply a :class:`~ade_engine.types.mapping.ColumnMappingPatch` to a mapped table."""

        assign = patch.assign or {}
        if assign:
            unknown = sorted(set(assign) - set(manifest.column_names))
            if unknown:
                raise ConfigError(f"Patch assigns unknown field(s): {', '.join(unknown)}")

        max_index = len(mapped.extracted.header)
        out_of_bounds = [idx for idx in assign.values() if idx < 0 or idx >= max_index]
        if out_of_bounds:
            raise ConfigError(f"Patch assigns column index out of bounds: {out_of_bounds}")

        current = {mf.field: mf.source_col for mf in mapped.mapping.fields}
        new_assignments = {**current, **assign}

        claimed: dict[int, str] = {}
        for field, source_col in new_assignments.items():
            if source_col is None:
                continue
            if source_col in claimed:
                raise ConfigError(f"Patch maps multiple fields to column {source_col + 1}")
            claimed[source_col] = field

        drop = patch.drop_passthrough or set()
        rename = patch.rename_passthrough or {}

        existing_passthrough = {p.source_col for p in mapped.mapping.passthrough}
        missing_drop = sorted(drop - existing_passthrough)
        if missing_drop:
            raise ConfigError(f"Patch cannot drop non-passthrough columns: {missing_drop}")

        missing_rename = sorted(set(rename) - existing_passthrough)
        if missing_rename:
            raise ConfigError(f"Patch cannot rename non-passthrough column(s): {missing_rename}")

        passthrough: list[PassthroughField] = []
        for p in mapped.mapping.passthrough:
            if p.source_col in drop:
                continue
            passthrough.append(
                PassthroughField(
                    source_col=p.source_col,
                    source_header=p.source_header,
                    output_name=rename.get(p.source_col, p.output_name),
                )
            )

        used_columns = {col for col in new_assignments.values() if col is not None}
        passthrough = [p for p in passthrough if p.source_col not in used_columns]

        patched_fields: list[MappedField] = []
        for field in manifest.column_names:
            source_col = new_assignments.get(field)
            if source_col is None:
                patched_fields.append(MappedField(field=field, source_col=None, source_header=None, score=None))
                continue

            header_value = mapped.extracted.header[source_col] if source_col < len(mapped.extracted.header) else ""
            patched_fields.append(MappedField(field=field, source_col=source_col, source_header=header_value, score=None))

        patched_mapping = ColumnMapping(fields=patched_fields, passthrough=passthrough)
        return MappedTable(
            origin=mapped.origin,
            region=mapped.region,
            mapping=patched_mapping,
            extracted=mapped.extracted,
            header=patched_mapping.output_header,
            rows=_project_rows(patched_mapping, mapped.extracted),
        )


__all__ = ["ColumnMapper", "MAPPING_SCORE_THRESHOLD", "COLUMN_SAMPLE_SIZE", "DEFAULT_REUSABLE_FIELDS"]
