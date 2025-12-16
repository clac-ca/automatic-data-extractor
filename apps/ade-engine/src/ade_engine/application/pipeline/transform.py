from __future__ import annotations

import logging
from typing import Any

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import TableView, TransformContext
from ade_engine.models.issues import IssuesPatch, merge_issues_patch
from ade_engine.models.patches import TablePatch, normalize_transform_return
from ade_engine.models.table import MappedColumn


def _is_missing(value: Any, *, settings: Settings) -> bool:
    if value is None:
        return True
    if settings.missing_values_mode == "none_or_blank":
        return isinstance(value, str) and not value.strip()
    return False


def _apply_values_patch(
    *,
    owner_field: str,
    values_patch: dict[str, list[Any]],
    columns: dict[str, list[Any]],
    mapping: dict[str, int | None],
    settings: Settings,
    row_count: int,
    logger: RunLogger,
) -> None:
    debug = logger.isEnabledFor(logging.DEBUG)
    for field, vec in values_patch.items():
        if field == owner_field:
            columns[field] = vec
            continue

        mode = settings.derived_write_mode
        if mode == "skip":
            continue

        existing = columns.get(field)
        if existing is None:
            existing = [None] * row_count
            columns[field] = existing
            mapping.setdefault(field, None)

        if len(existing) != row_count:
            raise PipelineError(
                f"Internal error: column '{field}' length mismatch ({len(existing)} vs {row_count})"
            )

        if mode == "overwrite":
            columns[field] = vec
            continue

        for idx, new_value in enumerate(vec):
            existing_value = existing[idx]
            if mode == "fill_missing":
                if _is_missing(existing_value, settings=settings):
                    existing[idx] = new_value
                continue

            if mode == "error_on_conflict":
                if _is_missing(existing_value, settings=settings) or _is_missing(new_value, settings=settings):
                    continue
                if existing_value != new_value:
                    raise PipelineError(
                        f"Derived field conflict for '{field}' at row {idx}: {existing_value!r} vs {new_value!r}"
                    )
                continue

            raise PipelineError(f"Unknown derived_write_mode: {mode}")

        if debug:
            logger.event(
                "transform.derived_merge",
                level=logging.DEBUG,
                data={"field": field, "mode": mode},
            )


def apply_transforms(
    *,
    mapped_columns: list[MappedColumn],
    columns: dict[str, list[Any]],
    mapping: dict[str, int | None],
    registry: Registry,
    settings: Settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
    row_count: int,
) -> TablePatch:
    """Apply transforms using the v2 column-vector contract.

    The engine owns ``columns`` + ``mapping`` and mutates them in place.
    Returns a TablePatch containing accumulated issues/meta.
    """

    registry_fields = set(registry.fields.keys())
    transforms_by_field = registry.column_transforms_by_field

    issues_patch: IssuesPatch = {}
    meta: dict[str, Any] = {}

    mapped_fields = [col.field_name for col in mapped_columns]
    mapped_set = set(mapped_fields)
    debug = logger.isEnabledFor(logging.DEBUG)

    def run_field_chain(field_name: str) -> None:
        transforms = transforms_by_field.get(field_name, [])
        if not transforms:
            return

        if field_name not in columns:
            columns[field_name] = [None] * row_count
            mapping.setdefault(field_name, None)

        for tf in transforms:
            before_sample = columns[field_name][:3] if debug else None
            ctx = TransformContext(
                field_name=field_name,
                column=list(columns[field_name]),
                table=TableView(columns, mapping=mapping, row_count=row_count),
                mapping=mapping,
                state=state,
                metadata=metadata,
                input_file_name=input_file_name,
                logger=logger,
            )
            raw_out = call_extension(tf.fn, ctx, label=f"Transform {tf.qualname}")
            patch = normalize_transform_return(
                field_name=field_name,
                raw=raw_out,
                row_count=row_count,
                registry_fields=registry_fields,
                source=f"Transform {tf.qualname}",
            )

            _apply_values_patch(
                owner_field=field_name,
                values_patch=patch.values,
                columns=columns,
                mapping=mapping,
                settings=settings,
                row_count=row_count,
                logger=logger,
            )
            merge_issues_patch(issues_patch, patch.issues)
            meta.update(patch.meta)

            if debug:
                logger.event(
                    "transform.result",
                    level=logging.DEBUG,
                    data={
                        "transform": tf.qualname,
                        "field": field_name,
                        "row_count": row_count,
                        "sample_before": before_sample,
                        "sample_after": columns[field_name][:3],
                        "emitted_fields": sorted(patch.values.keys()),
                        "emitted_issue_fields": sorted(patch.issues.keys()),
                    },
                )

    # Phase 1: mapped fields in source order.
    for field_name in mapped_fields:
        run_field_chain(field_name)

    # Phase 2: derived-only fields that now exist and have transforms.
    phase2_done: set[str] = set()
    while True:
        progressed = False
        for field_name in registry.fields.keys():
            if field_name in mapped_set or field_name in phase2_done:
                continue
            if field_name not in columns:
                continue
            if not transforms_by_field.get(field_name):
                continue
            run_field_chain(field_name)
            phase2_done.add(field_name)
            progressed = True
        if not progressed:
            break

    return TablePatch(issues=issues_patch, meta=meta)


__all__ = ["apply_transforms"]
