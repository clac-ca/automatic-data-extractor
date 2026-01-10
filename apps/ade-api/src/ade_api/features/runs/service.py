"""Run orchestration service coordinating DB state and queueing."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import openpyxl
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.common.types import OrderBy
from ade_api.common.workbook_preview import (
    WorkbookSheetPreview,
    build_workbook_preview_from_csv,
    build_workbook_preview_from_xlsx,
)
from ade_api.features.configs.deps import compute_dependency_digest
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.workspaces.repository import WorkspacesRepository
from ade_api.features.workspaces.settings import read_processing_paused
from ade_api.infra.storage import (
    workspace_documents_root,
    workspace_run_root,
)
from ade_api.models import (
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentStatus,
    Run,
    RunField,
    RunMetrics,
    RunStatus,
    RunTableColumn,
)
from ade_api.settings import Settings

from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunOutputPreviewParseError,
    RunOutputPreviewSheetNotFoundError,
    RunOutputPreviewUnsupportedError,
    RunOutputSheetParseError,
    RunOutputSheetUnsupportedError,
    RunQueueFullError,
)
from .filters import RunColumnFilters
from .repository import RunsRepository
from .schemas import (
    RunBatchCreateOptions,
    RunCreateOptions,
    RunCreateOptionsBase,
    RunInput,
    RunLinks,
    RunOutput,
    RunOutputSheet,
    RunPage,
    RunResource,
)

__all__ = [
    "RunInputMissingError",
    "RunDocumentMissingError",
    "RunLogsFileMissingError",
    "RunNotFoundError",
    "RunOutputNotReadyError",
    "RunOutputMissingError",
    "RunsService",
]

logger = logging.getLogger(__name__)

_DEPS_DIGEST_CACHE_SIZE = 256


@lru_cache(maxsize=_DEPS_DIGEST_CACHE_SIZE)
def _cached_deps_digest(config_path: str, content_digest: str) -> str:
    return compute_dependency_digest(Path(config_path))


def _deps_digest_cache_key(configuration: Configuration) -> str:
    if configuration.content_digest:
        return configuration.content_digest
    if configuration.updated_at:
        return configuration.updated_at.isoformat()
    return "unknown"



# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RunPathsSnapshot:
    """Container for run-relative output paths.

    This is the normalized view that higher layers use. All paths here are
    relative to the runs root, so they are safe to surface externally.
    """

    output_path: str | None = None
    processed_file: str | None = None


def _run_with_timeout(func, *, timeout: float, **kwargs):
    """Run a callable with a timeout to avoid hanging on large workbook operations."""
    if timeout <= 0:
        return func(**kwargs)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, **kwargs)
        return future.result(timeout=timeout)



# --------------------------------------------------------------------------- #
# Main service
# --------------------------------------------------------------------------- #


class RunsService:
    """Coordinate run persistence, queueing, and serialization for the API.

    Responsibilities:
    - create and persist Run rows
    - enforce queue limits and batch creation rules
    - read artifacts/logs written by ade-worker
    - serialize run resources for API responses
    """

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        storage: ConfigStorage | None = None,
    ) -> None:
        from ade_api.features.documents.service import DocumentsService

        self._session = session
        self._settings = settings
        self._configs = ConfigurationsRepository(session)
        self._runs = RunsRepository(session)
        self._documents = DocumentsRepository(session)
        self._workspaces = WorkspacesRepository(session)
        self._storage = storage or ConfigStorage(
            settings=settings,
        )
        self._documents_service = DocumentsService(session=session, settings=settings)

        if settings.documents_dir is None:
            raise RuntimeError("ADE_DOCUMENTS_DIR is not configured")
        if settings.runs_dir is None:
            raise RuntimeError("ADE_RUNS_DIR is not configured")

        self._runs_dir = Path(settings.runs_dir)
        default_max = Run.__table__.c.max_attempts.default
        self._run_max_attempts = int(default_max.arg) if default_max is not None else 3

    # --------------------------------------------------------------------- #
    # Run lifecycle: creation and queueing
    # --------------------------------------------------------------------- #

    def prepare_run(
        self,
        *,
        configuration_id: UUID,
        options: RunCreateOptions,
    ) -> Run:
        """Create the queued run row and enqueue execution."""

        logger.debug(
            "run.prepare.start",
            extra=log_context(
                configuration_id=configuration_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
                input_document_id=options.input_document_id,
            ),
        )

        configuration = self._resolve_configuration(configuration_id)

        input_document_id = options.input_document_id
        if not input_document_id:
            raise RunInputMissingError("Input document is required to create a run")
        self._require_document(
            workspace_id=configuration.workspace_id,
            document_id=input_document_id,
        )

        existing = self._runs.list_active_for_documents(
            configuration_id=configuration.id,
            document_ids=[input_document_id],
        )
        if existing:
            run = existing[0]
            configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
            self._session.flush()
            logger.info(
                "run.prepare.noop",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    input_document_id=input_document_id,
                    status=run.status.value,
                ),
            )
            return run

        self._enforce_queue_capacity()

        selected_sheet_names = self._select_input_sheet_names(options)
        run_options_payload = options.model_dump(mode="json", exclude_none=True)
        deps_digest = self._resolve_deps_digest(configuration)
        engine_spec = self._settings.engine_spec
        self._insert_runs_for_documents(
            configuration=configuration,
            document_ids=[input_document_id],
            engine_spec=engine_spec,
            deps_digest=deps_digest,
            input_sheet_names_by_document_id={
                input_document_id: selected_sheet_names or None,
            },
            run_options_by_document_id={
                input_document_id: run_options_payload,
            },
            document_status=None,
            existing_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
        )

        # Touch configuration usage timestamp.
        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
        self._session.flush()

        run = self._require_active_run(
            configuration_id=configuration.id,
            document_id=input_document_id,
        )

        logger.info(
            "run.prepare.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                input_document_id=input_document_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )
        return run

    def prepare_run_for_workspace(
        self,
        *,
        workspace_id: UUID,
        input_document_id: UUID,
        configuration_id: UUID | None,
        options: RunCreateOptionsBase | None = None,
    ) -> Run:
        """Create a run for the workspace, resolving the active configuration if needed."""

        configuration = self._resolve_workspace_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        run_options = self._merge_run_options(
            input_document_id=input_document_id,
            options=options,
        )
        return self.prepare_run(
            configuration_id=configuration.id,
            options=run_options,
        )

    def prepare_runs_batch(
        self,
        *,
        configuration_id: UUID,
        document_ids: Sequence[UUID],
        options: RunBatchCreateOptions,
        input_sheet_names_by_document_id: dict[UUID, list[str]] | None = None,
        active_sheet_only_by_document_id: dict[UUID, bool] | None = None,
        skip_existing_check: bool = False,
        queued_count: int | None = None,
    ) -> list[Run]:
        """Create queued runs for each document id, enforcing all-or-nothing semantics."""

        logger.debug(
            "run.prepare.batch.start",
            extra=log_context(
                configuration_id=configuration_id,
                document_count=len(document_ids),
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )

        if not document_ids:
            return []

        configuration = self._resolve_configuration(configuration_id)
        self._require_documents(
            workspace_id=configuration.workspace_id,
            document_ids=document_ids,
        )

        batch_active_sheet_only = bool(getattr(options, "active_sheet_only", False))
        normalized_sheet_names: dict[UUID, list[str] | None] = {}
        active_sheet_only_lookup: dict[UUID, bool] = {}
        run_options_by_document_id: dict[UUID, RunCreateOptions] = {}

        if skip_existing_check:
            new_document_ids = list(document_ids)
        else:
            existing = self._runs.list_active_for_documents(
                configuration_id=configuration.id,
                document_ids=list(document_ids),
            )
            existing_ids = {run.input_document_id for run in existing}
            new_document_ids = [doc_id for doc_id in document_ids if doc_id not in existing_ids]

        if new_document_ids:
            self._enforce_queue_capacity(
                requested=len(new_document_ids),
                queued_count=queued_count,
            )

            for document_id in new_document_ids:
                input_sheet_names = None
                if (
                    input_sheet_names_by_document_id
                    and document_id in input_sheet_names_by_document_id
                ):
                    raw_names = input_sheet_names_by_document_id.get(document_id) or []
                    normalized = self._select_input_sheet_names(
                        RunCreateOptions(
                            input_document_id=document_id,
                            input_sheet_names=raw_names,
                        ),
                    )
                    input_sheet_names = normalized or None
                active_sheet_only = batch_active_sheet_only
                if (
                    active_sheet_only_by_document_id
                    and document_id in active_sheet_only_by_document_id
                ):
                    active_sheet_only = bool(active_sheet_only_by_document_id.get(document_id))
                if input_sheet_names:
                    active_sheet_only = False
                normalized_sheet_names[document_id] = input_sheet_names
                active_sheet_only_lookup[document_id] = active_sheet_only
                run_options_by_document_id[document_id] = RunCreateOptions(
                    dry_run=options.dry_run,
                    validate_only=options.validate_only,
                    log_level=options.log_level,
                    input_document_id=document_id,
                    input_sheet_names=input_sheet_names,
                    active_sheet_only=active_sheet_only,
                    metadata=options.metadata,
                )

            deps_digest = self._resolve_deps_digest(configuration)
            engine_spec = self._settings.engine_spec
            self._insert_runs_for_documents(
                configuration=configuration,
                document_ids=new_document_ids,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                input_sheet_names_by_document_id=normalized_sheet_names,
                run_options_by_document_id={
                    doc_id: run_options.model_dump(mode="json", exclude_none=True)
                    for doc_id, run_options in run_options_by_document_id.items()
                },
                document_status=None,
                existing_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
            )

        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
        self._session.flush()

        runs = self._runs.list_active_for_documents(
            configuration_id=configuration.id,
            document_ids=list(document_ids),
        )

        if runs:
            logger.info(
                "run.prepare.batch.success",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    count=len(runs),
                ),
            )
        return runs

    def prepare_runs_batch_for_workspace(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        configuration_id: UUID | None,
        options: RunBatchCreateOptions,
    ) -> list[Run]:
        """Create batch runs for the workspace, resolving the active configuration if needed."""

        configuration = self._resolve_workspace_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        return self.prepare_runs_batch(
            configuration_id=configuration.id,
            document_ids=document_ids,
            options=options,
        )

    def load_run_options(self, run: Run) -> RunCreateOptions:
        """Rehydrate run options from the run row."""

        payload: dict[str, Any] = dict(run.run_options or {})

        if "input_document_id" not in payload and run.input_document_id:
            payload["input_document_id"] = str(run.input_document_id)
        if "input_sheet_names" not in payload and run.input_sheet_names:
            payload["input_sheet_names"] = list(run.input_sheet_names)

        try:
            return RunCreateOptions(**payload)
        except Exception:
            logger.warning(
                "run.options.load.failed",
                extra=log_context(run_id=run.id),
            )
            return RunCreateOptions(
                input_document_id=str(run.input_document_id),
                input_sheet_names=list(run.input_sheet_names or []),
            )

    def enqueue_pending_runs_for_configuration(
        self,
        *,
        configuration_id: UUID,
        batch_size: int | None = None,
    ) -> int:
        """Queue runs for uploaded documents without runs using the active configuration."""

        try:
            configuration = self._resolve_configuration(configuration_id)
        except ConfigurationNotFoundError:
            return 0
        if self._processing_paused(configuration.workspace_id):
            logger.info(
                "run.pending.enqueue.skip.processing_paused",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                ),
            )
            return 0
        if configuration.status is not ConfigurationStatus.ACTIVE:
            logger.info(
                "run.pending.enqueue.skip.inactive_config",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
            return 0

        queue_limit = self._settings.queue_size
        batch_size = batch_size or queue_limit or 100
        if batch_size <= 0:
            return 0

        total = 0
        while True:
            queued_count = None
            remaining = None
            if queue_limit:
                queued_count = self._runs.count_queued()
                remaining = max(queue_limit - queued_count, 0)
                if remaining <= 0:
                    break
            limit = batch_size if remaining is None else min(batch_size, remaining)
            documents = self._pending_documents(
                workspace_id=configuration.workspace_id,
                configuration_id=configuration.id,
                limit=limit,
            )
            if not documents:
                break
            logger.debug(
                "run.pending.enqueue.batch batch_size=%s queued_count=%s remaining=%s",
                limit,
                queued_count,
                remaining,
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    batch_size=limit,
                    queued_count=queued_count,
                    remaining=remaining,
                ),
            )
            document_ids = [doc.id for doc in documents]
            sheet_names_by_document_id: dict[UUID, list[str]] = {}
            active_sheet_only_by_document_id: dict[UUID, bool] = {}
            for document in documents:
                run_options = self._documents_service.read_upload_run_options(document.attributes)
                if run_options and run_options.input_sheet_names is not None:
                    sheet_names_by_document_id[document.id] = list(run_options.input_sheet_names)
                if run_options and run_options.active_sheet_only:
                    active_sheet_only_by_document_id[document.id] = True
            try:
                runs = self.prepare_runs_batch(
                    configuration_id=configuration.id,
                    document_ids=document_ids,
                    options=RunBatchCreateOptions(),
                    input_sheet_names_by_document_id=sheet_names_by_document_id or None,
                    active_sheet_only_by_document_id=active_sheet_only_by_document_id or None,
                    skip_existing_check=True,
                    queued_count=queued_count,
                )
            except RunQueueFullError:
                logger.warning(
                    "run.pending.enqueue.queue_full",
                    extra=log_context(
                        workspace_id=configuration.workspace_id,
                        configuration_id=configuration.id,
                    ),
                )
                break
            total += len(runs)
            if len(document_ids) < limit:
                break

        if total:
            logger.info(
                "run.pending.enqueue.completed",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    count=total,
                ),
            )
        return total

    def is_processing_paused(self, *, workspace_id: UUID) -> bool:
        return self._processing_paused(workspace_id)

    def _remaining_queue_capacity(self) -> int | None:
        limit = self._settings.queue_size
        if not limit:
            return None
        queued = self._runs.count_queued()
        return max(limit - queued, 0)

    def _pending_documents(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        limit: int,
    ) -> list[Document]:
        if limit <= 0:
            return []
        pending_run_exists = (
            select(Run.id)
            .where(
                Run.input_document_id == Document.id,
                Run.configuration_id == configuration_id,
            )
            .limit(1)
            .exists()
        )
        stmt = (
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == DocumentStatus.UPLOADED,
                Document.deleted_at.is_(None),
                ~pending_run_exists,
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def _require_active_run(
        self,
        *,
        configuration_id: UUID,
        document_id: UUID,
    ) -> Run:
        runs = self._runs.list_active_for_documents(
            configuration_id=configuration_id,
            document_ids=[document_id],
        )
        if not runs:
            raise RuntimeError(f"No active run found for document {document_id}")
        return runs[0]

    def _resolve_deps_digest(self, configuration: Configuration) -> str:
        try:
            config_path = self._storage.ensure_config_path(
                configuration.workspace_id,
                configuration.id,
            )
        except Exception as exc:  # pragma: no cover - surface as run error
            raise RunInputMissingError("Configuration files are missing") from exc
        cache_key = _deps_digest_cache_key(configuration)
        return _cached_deps_digest(str(config_path), cache_key)

    def _insert_runs_for_documents(
        self,
        *,
        configuration: Configuration,
        document_ids: Sequence[UUID],
        engine_spec: str,
        deps_digest: str,
        input_sheet_names_by_document_id: dict[UUID, list[str] | None] | None,
        run_options_by_document_id: dict[UUID, dict[str, Any] | None] | None,
        document_status: DocumentStatus | None,
        existing_statuses: Sequence[RunStatus] | None,
    ) -> None:
        if not document_ids:
            return

        base_stmt = select(Document.id).where(
            Document.workspace_id == configuration.workspace_id,
            Document.deleted_at.is_(None),
            Document.id.in_(document_ids),
        )
        if document_status is not None:
            base_stmt = base_stmt.where(Document.status == document_status)
        result = self._session.execute(base_stmt)
        eligible_ids = [doc_id for (doc_id,) in result.all()]
        if not eligible_ids:
            return

        if existing_statuses:
            existing_stmt = select(Run.input_document_id).where(
                Run.configuration_id == configuration.id,
                Run.input_document_id.in_(eligible_ids),
                Run.status.in_(list(existing_statuses)),
            )
            existing_result = self._session.execute(existing_stmt)
            existing_ids = {doc_id for (doc_id,) in existing_result.all()}
            eligible_ids = [doc_id for doc_id in eligible_ids if doc_id not in existing_ids]
            if not eligible_ids:
                return

        def build_rows(ids: Sequence[UUID]) -> list[dict[str, Any]]:
            now = utc_now()
            return [
                {
                    "id": uuid4(),
                    "configuration_id": configuration.id,
                    "workspace_id": configuration.workspace_id,
                    "input_document_id": doc_id,
                    "input_sheet_names": (
                        input_sheet_names_by_document_id.get(doc_id)
                        if input_sheet_names_by_document_id
                        else None
                    ),
                    "run_options": (
                        run_options_by_document_id.get(doc_id)
                        if run_options_by_document_id
                        else None
                    ),
                    "engine_spec": engine_spec,
                    "deps_digest": deps_digest,
                    "status": RunStatus.QUEUED,
                    "available_at": now,
                    "attempt_count": 0,
                    "max_attempts": self._run_max_attempts,
                }
                for doc_id in ids
            ]

        rows = build_rows(eligible_ids)
        for attempt in range(2):
            try:
                with self._session.begin_nested():
                    self._session.execute(insert(Run), rows)
                return
            except IntegrityError:
                if attempt:
                    raise
                if existing_statuses:
                    existing_stmt = select(Run.input_document_id).where(
                        Run.configuration_id == configuration.id,
                        Run.input_document_id.in_(eligible_ids),
                        Run.status.in_(list(existing_statuses)),
                    )
                    existing_result = self._session.execute(existing_stmt)
                    existing_ids = {doc_id for (doc_id,) in existing_result.all()}
                    remaining = [doc_id for doc_id in eligible_ids if doc_id not in existing_ids]
                    if not remaining:
                        return
                    rows = build_rows(remaining)

    def _enforce_queue_capacity(
        self,
        *,
        requested: int = 1,
        queued_count: int | None = None,
    ) -> None:
        limit = self._settings.queue_size
        if not limit or requested <= 0:
            return

        queued = queued_count if queued_count is not None else self._runs.count_queued()
        if queued + requested > limit:
            raise RunQueueFullError(f"Run queue is full (limit {limit})")

    # --------------------------------------------------------------------- #
    # Public read APIs (runs, summaries, outputs)
    # --------------------------------------------------------------------- #

    def get_run(self, run_id: UUID) -> Run | None:
        """Return the run instance for ``run_id`` if it exists."""

        logger.debug(
            "run.get.start",
            extra=log_context(run_id=run_id),
        )
        run = self._runs.get(run_id)
        if run is None:
            logger.debug(
                "run.get.miss",
                extra=log_context(run_id=run_id),
            )
        else:
            logger.debug(
                "run.get.hit",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    status=run.status.value,
                ),
            )
        return run

    def get_run_metrics(self, *, run_id: UUID) -> RunMetrics | None:
        """Return persisted run metrics for ``run_id`` when available."""

        run = self._require_run(run_id)
        return self._runs.get_metrics(run.id)

    def list_run_fields(self, *, run_id: UUID) -> list[RunField]:
        """Return field summaries for ``run_id``."""

        run = self._require_run(run_id)
        return self._runs.list_fields(run.id)

    def list_run_columns(
        self,
        *,
        run_id: UUID,
        filters: RunColumnFilters,
    ) -> list[RunTableColumn]:
        """Return detected columns for ``run_id`` with optional filters."""

        run = self._require_run(run_id)
        return self._runs.list_columns(run_id=run.id, filters=filters)

    def list_runs(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None = None,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        page: int,
        per_page: int,
    ) -> RunPage:
        """Return paginated runs for ``workspace_id`` with optional filters."""

        logger.debug(
            "run.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                filters=[item.model_dump() for item in filters],
                order_by=str(order_by),
                page=page,
                per_page=per_page,
                q=q,
            ),
        )

        page_result = self._runs.list_by_workspace(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            filters=filters,
            join_operator=join_operator,
            q=q,
            order_by=order_by,
            page=page,
            per_page=per_page,
        )
        resources = [self.to_resource(run, resolve_paths=False) for run in page_result.items]
        response = RunPage(
            items=resources,
            page=page_result.page,
            per_page=page_result.per_page,
            page_count=page_result.page_count,
            total=page_result.total,
            changes_cursor=page_result.changes_cursor,
        )

        logger.info(
            "run.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                page=response.page,
                per_page=response.per_page,
                count=len(response.items),
                total=response.total,
            ),
        )
        return response

    def list_runs_for_configuration(
        self,
        *,
        configuration_id: UUID,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        page: int,
        per_page: int,
    ) -> RunPage:
        """Return paginated runs for ``configuration_id`` scoped to its workspace."""

        configuration = self._resolve_configuration(configuration_id)
        return self.list_runs(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            filters=filters,
            join_operator=join_operator,
            q=q,
            order_by=order_by,
            page=page,
            per_page=per_page,
        )

    def to_resource(self, run: Run, *, resolve_paths: bool = True) -> RunResource:
        """Convert ``run`` into its API representation."""

        run_dir = (
            self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
            if resolve_paths
            else None
        )
        paths = (
            self._finalize_paths(
                run_dir=run_dir,
                default_paths=RunPathsSnapshot(output_path=run.output_path),
            )
            if resolve_paths and run_dir is not None
            else RunPathsSnapshot(output_path=run.output_path)
        )

        processed_file = self._resolve_processed_file(paths=paths) if resolve_paths else None

        # Timing and failure info
        started_at = self._ensure_utc(run.started_at)
        completed_at = self._ensure_utc(run.completed_at)
        duration_seconds = (
            (completed_at - started_at).total_seconds() if started_at and completed_at else None
        )

        failure_code = None
        failure_stage = None
        failure_message = run.error_message

        input_meta = self._build_input_metadata(
            run=run,
            files_counts={},
            sheets_counts={},
        )
        output_meta = self._build_output_metadata(
            run=run,
            run_dir=run_dir,
            paths=paths,
            processed_file=processed_file,
            resolve_paths=resolve_paths,
        )
        links = self._links(run.id)

        return RunResource(
            id=run.id,
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            status=run.status,
            failure_code=failure_code,
            failure_stage=failure_stage,
            failure_message=failure_message,
            created_at=self._ensure_utc(run.created_at) or utc_now(),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            exit_code=run.exit_code,
            input=input_meta,
            output=output_meta,
            links=links,
            events_stream_url=links.events_stream,
            events_download_url=links.events_download,
        )

    def _resolve_processed_file(
        self,
        *,
        paths: RunPathsSnapshot,
    ) -> str | None:
        processed_file = paths.processed_file
        return processed_file

    def _build_input_metadata(
        self,
        *,
        run: Run,
        files_counts: dict[str, Any],
        sheets_counts: dict[str, Any],
    ) -> RunInput:
        document_id = str(run.input_document_id) if run.input_document_id else None
        filename: str | None = None
        content_type: str | None = None
        size_bytes: int | None = None
        download_url: str | None = None

        if document_id:
            download_url = f"/api/v1/runs/{run.id}/input/download"
            try:
                document = self._require_document(
                    workspace_id=run.workspace_id,
                    document_id=run.input_document_id,  # type: ignore[arg-type]
                )
                filename = document.original_filename
                content_type = document.content_type
                size_bytes = document.byte_size
            except RunDocumentMissingError:
                logger.warning(
                    "run.input.metadata.missing_document",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        document_id=document_id,
                    ),
                )

        return RunInput(
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            download_url=download_url,
            input_sheet_names=run.input_sheet_names,
            input_file_count=files_counts.get("total"),
            input_sheet_count=sheets_counts.get("total"),
        )

    def _build_output_metadata(
        self,
        *,
        run: Run,
        run_dir: Path | None,
        paths: RunPathsSnapshot,
        processed_file: str | None,
        resolve_paths: bool = True,
    ) -> RunOutput:
        output_path = paths.output_path
        output_file: Path | None = None
        if resolve_paths and run_dir is not None and output_path:
            candidate = (run_dir / output_path).resolve()
            try:
                candidate.relative_to(run_dir)
            except ValueError:
                candidate = None
            if candidate and candidate.is_file():
                output_file = candidate

        ready = run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED} and (
            bool(output_file) if resolve_paths else bool(output_path)
        )

        filename: str | None = None
        size_bytes: int | None = None
        content_type: str | None = None

        if output_file:
            filename = output_file.name
            try:
                size_bytes = output_file.stat().st_size
            except OSError:
                size_bytes = None
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        elif output_path:
            filename = Path(output_path).name

        return RunOutput(
            ready=ready,
            download_url=f"/api/v1/runs/{run.id}/output/download",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            has_output=bool(output_file) if resolve_paths else bool(output_path),
            output_path=output_path,
            processed_file=str(processed_file) if processed_file else None,
        )

    @staticmethod
    def _links(run_id: UUID) -> RunLinks:
        base = f"/api/v1/runs/{run_id}"
        events_stream = f"{base}/events/stream"
        events_download = f"{base}/events/download"
        output_metadata = f"{base}/output"
        output_download = f"{output_metadata}/download"
        input_metadata = f"{base}/input"
        input_download = f"{input_metadata}/download"

        return RunLinks(
            self=base,
            events_stream=events_stream,
            events_download=events_download,
            logs=events_download,
            input=input_metadata,
            input_download=input_download,
            output=output_download,
            output_download=output_download,
            output_metadata=output_metadata,
        )

    def get_run_input_metadata(
        self,
        *,
        run_id: UUID,
    ) -> RunInput:
        run = self._require_run(run_id)
        resource = self.to_resource(run)
        if resource.input.document_id is None:
            raise RunInputMissingError("Run input is unavailable")
        if resource.input.filename is None:
            raise RunDocumentMissingError("Run input file is unavailable")
        return resource.input

    def stream_run_input(
        self,
        *,
        run_id: UUID,
    ) -> tuple[Run, Document, Iterator[bytes]]:
        run = self._require_run(run_id)
        if not run.input_document_id:
            raise RunInputMissingError("Run input is unavailable")
        document = self._require_document(
            workspace_id=run.workspace_id,
            document_id=run.input_document_id,
        )
        storage = self._storage_for(run.workspace_id)
        path = storage.path_for(document.stored_uri)
        if not path.exists():
            logger.warning(
                "run.input.stream.missing_file",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    document_id=document.id,
                    stored_uri=document.stored_uri,
                ),
            )
            raise RunDocumentMissingError("Run input file is unavailable")

        stream = storage.stream(document.stored_uri)

        def _guarded() -> Iterator[bytes]:
            try:
                for chunk in stream:
                    yield chunk
            except FileNotFoundError as exc:
                logger.warning(
                    "run.input.stream.file_lost",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        document_id=document.id,
                        stored_uri=document.stored_uri,
                    ),
                )
                raise RunDocumentMissingError("Run input file is unavailable") from exc

        return run, document, _guarded()

    def get_run_output_metadata(
        self,
        *,
        run_id: UUID,
    ) -> RunOutput:
        run = self._require_run(run_id)
        resource = self.to_resource(run)
        return resource.output

    def resolve_output_for_download(
        self,
        *,
        run_id: UUID,
    ) -> tuple[Run, Path]:
        run = self._require_run(run_id)
        if run.status in {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
        }:
            raise RunOutputNotReadyError("Run output is not available until the run completes.")
        try:
            path = self.resolve_output_file(run_id=run_id)
        except RunOutputMissingError as err:
            if run.status is RunStatus.FAILED:
                raise RunOutputMissingError(
                    "Run failed and no output is available",
                ) from err
            raise
        return run, path

    def get_run_output_preview(
        self,
        *,
        run_id: UUID,
        max_rows: int,
        max_columns: int,
        trim_empty_columns: bool = False,
        trim_empty_rows: bool = False,
        sheet_name: str | None = None,
        sheet_index: int | None = None,
    ) -> WorkbookSheetPreview:
        """Return a table-ready preview for a run output workbook."""

        effective_sheet_index = sheet_index
        if sheet_name is None and sheet_index is None:
            effective_sheet_index = 0

        logger.debug(
            "run.output.preview.start",
            extra=log_context(
                run_id=run_id,
                sheet_name=sheet_name,
                sheet_index=effective_sheet_index,
            ),
        )

        run, path = self.resolve_output_for_download(run_id=run_id)
        suffix = path.suffix.lower()
        timeout = self._settings.preview_timeout_seconds

        try:
            if suffix == ".xlsx":
                preview = _run_with_timeout(
                    build_workbook_preview_from_xlsx,
                    timeout=timeout,
                    path=path,
                    max_rows=max_rows,
                    max_columns=max_columns,
                    trim_empty_columns=trim_empty_columns,
                    trim_empty_rows=trim_empty_rows,
                    sheet_name=sheet_name,
                    sheet_index=effective_sheet_index,
                )
            elif suffix == ".csv":
                preview = _run_with_timeout(
                    build_workbook_preview_from_csv,
                    timeout=timeout,
                    path=path,
                    max_rows=max_rows,
                    max_columns=max_columns,
                    trim_empty_columns=trim_empty_columns,
                    trim_empty_rows=trim_empty_rows,
                    sheet_name=sheet_name,
                    sheet_index=effective_sheet_index,
                )
            else:
                raise RunOutputPreviewUnsupportedError(
                    f"Preview is not supported for output file type {suffix!r}."
                )
        except (KeyError, IndexError) as exc:
            requested = sheet_name if sheet_name is not None else str(effective_sheet_index)
            raise RunOutputPreviewSheetNotFoundError(
                f"Sheet {requested!r} was not found in run {run_id!r} output."
            ) from exc
        except FuturesTimeout as exc:
            raise RunOutputPreviewParseError(
                f"Preview timed out after {timeout:g}s for run {run_id!r} output."
            ) from exc
        except RunOutputPreviewUnsupportedError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise RunOutputPreviewParseError(
                f"Preview generation failed for run {run_id!r} output ({type(exc).__name__})."
            ) from exc

        logger.info(
            "run.output.preview.success",
            extra=log_context(
                run_id=run.id,
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                sheet_name=preview.name,
                sheet_index=preview.index,
            ),
        )
        return preview

    def list_run_output_sheets(
        self,
        *,
        run_id: UUID,
    ) -> list[RunOutputSheet]:
        """Return worksheet metadata for a run output workbook."""

        logger.debug(
            "run.output.sheets.list.start",
            extra=log_context(run_id=run_id),
        )

        run, path = self.resolve_output_for_download(run_id=run_id)
        suffix = path.suffix.lower()
        timeout = self._settings.preview_timeout_seconds

        if suffix == ".xlsx":
            try:
                sheets = _run_with_timeout(self._inspect_workbook, timeout=timeout, path=path)
            except FuturesTimeout as exc:
                raise RunOutputSheetParseError(
                    f"Worksheet inspection timed out after {timeout:g}s for run {run_id!r} output."
                ) from exc
            except Exception as exc:  # pragma: no cover - defensive fallback
                raise RunOutputSheetParseError(
                    f"Worksheet inspection failed for run {run_id!r} output ({type(exc).__name__})."
                ) from exc
            logger.info(
                "run.output.sheets.list.success",
                extra=log_context(
                    run_id=run.id,
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    sheet_count=len(sheets),
                    kind="workbook",
                ),
            )
            return sheets

        if suffix == ".csv":
            name = self._default_sheet_name(path.name)
            sheets = [RunOutputSheet(name=name, index=0, kind="file", is_active=True)]
            logger.info(
                "run.output.sheets.list.success",
                extra=log_context(
                    run_id=run.id,
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    sheet_count=len(sheets),
                    kind="file",
                ),
            )
            return sheets

        raise RunOutputSheetUnsupportedError(
            f"Sheets are not supported for output file type {suffix!r}."
        )

    def get_logs_file_path(self, *, run_id: UUID) -> Path:
        """Return the raw log stream path for ``run_id`` when available."""

        logger.debug(
            "run.logs.file_path.start",
            extra=log_context(run_id=run_id),
        )
        run = self._require_run(run_id)
        logs_path = self.get_event_log_path(run_id=run_id)
        if not logs_path.is_file():
            logger.warning(
                "run.logs.file_path.missing",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(logs_path),
                ),
            )
            raise RunLogsFileMissingError("Run log stream is unavailable")
        logger.info(
            "run.logs.file_path.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                path=str(logs_path),
            ),
        )
        return logs_path

    def get_event_log_path(self, *, run_id: UUID) -> Path:
        """Return the NDJSON log path for a run (may not exist yet)."""

        run = self._require_run(run_id)
        logs_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "logs"
        return logs_dir / "events.ndjson"

    def resolve_output_file(
        self,
        *,
        run_id: UUID,
    ) -> Path:
        """Return the absolute path for ``relative_path`` in ``run_id`` outputs."""

        logger.debug(
            "run.outputs.resolve.start",
            extra=log_context(run_id=run_id),
        )
        run = self._require_run(run_id)
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)

        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(output_path=run.output_path),
        )
        output_relative = paths_snapshot.output_path
        if not output_relative:
            logger.warning(
                "run.outputs.resolve.missing_root",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(run_dir / "output"),
                ),
            )
            raise RunOutputMissingError("Run output is unavailable")

        candidate = (run_dir / output_relative).resolve()
        try:
            candidate.relative_to(run_dir)
        except ValueError:
            logger.warning(
                "run.outputs.resolve.outside_directory",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(candidate),
                ),
            )
            raise RunOutputMissingError("Requested output is outside the run directory") from None

        if not candidate.is_file():
            logger.warning(
                "run.outputs.resolve.not_found",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(candidate),
                ),
            )
            raise RunOutputMissingError("Requested output file not found")

        logger.info(
            "run.outputs.resolve.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                path=str(candidate),
            ),
        )
        return candidate

    def run_directory(self, *, workspace_id: UUID, run_id: UUID) -> Path:
        """Return the canonical run directory for a given ``run_id``."""

        path = self._run_dir_for_run(workspace_id=workspace_id, run_id=run_id)
        logger.debug(
            "run.directory.resolve",
            extra=log_context(workspace_id=workspace_id, run_id=run_id, path=str(path)),
        )
        return path

    def run_relative_path(self, path: Path, *, base_dir: Path | None = None) -> str:
        """Return ``path`` relative to ``base_dir`` (or runs root), validating traversal."""

        root = (base_dir or self._runs_dir).resolve()
        candidate = path.resolve()
        try:
            value = str(candidate.relative_to(root))
        except ValueError:  # pragma: no cover - defensive guard
            logger.warning(
                "run.path.escape_detected",
                extra=log_context(path=str(candidate)),
            )
            raise RunOutputMissingError("Requested path escapes runs directory") from None
        return value

    # --------------------------------------------------------------------- #
    # Internal helpers: paths, summaries, manifests
    # --------------------------------------------------------------------- #

    def _relative_if_exists(
        self,
        path: str | Path | None,
        *,
        run_dir: Path | None = None,
    ) -> str | None:
        if path is None:
            return None

        candidates: list[Path] = []
        candidate = Path(path)
        candidates.append(candidate)
        if run_dir is not None and not candidate.is_absolute():
            candidates.append(run_dir / candidate)

        for option in candidates:
            if not option.exists():
                continue
            try:
                return self.run_relative_path(option, base_dir=run_dir)
            except RunOutputMissingError:
                continue
        return None

    def _relative_output_path(self, output_dir: Path, run_dir: Path) -> str | None:
        if not output_dir.exists() or not output_dir.is_dir():
            return None
        normalized = output_dir / "normalized.xlsx"
        relative = self._relative_if_exists(normalized, run_dir=run_dir)
        if relative:
            return relative
        for path in output_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = self._relative_if_exists(path, run_dir=run_dir)
            if relative is not None:
                return relative
        return None

    def _run_relative_hint(self, path: str | Path | None, *, run_dir: Path | None) -> str | None:
        """Return ``path`` relative to the run directory without hitting the filesystem."""

        if path is None or run_dir is None:
            return None

        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (run_dir / candidate).resolve()
        try:
            return self.run_relative_path(candidate, base_dir=run_dir)
        except RunOutputMissingError:
            return None

    @staticmethod
    def _document_descriptor(document: Document) -> dict[str, Any]:
        return {
            "document_id": str(document.id),
            "display_name": document.original_filename,
            "name": document.original_filename,
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "byte_size": document.byte_size,
        }

    def _finalize_paths(
        self,
        *,
        run_dir: Path,
        default_paths: RunPathsSnapshot,
    ) -> RunPathsSnapshot:
        """Merge inferred filesystem paths for outputs."""

        snapshot = RunPathsSnapshot(
            output_path=default_paths.output_path,
            processed_file=default_paths.processed_file,
        )

        # Output path: if not provided, infer from <run_dir>/output.
        if snapshot.output_path:
            snapshot.output_path = self._run_relative_hint(snapshot.output_path, run_dir=run_dir)
        if not snapshot.output_path:
            snapshot.output_path = self._relative_output_path(run_dir / "output", run_dir)

        return snapshot

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return None

    def _require_run(self, run_id: UUID) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            logger.warning(
                "run.require_run.not_found",
                extra=log_context(run_id=run_id),
            )
            raise RunNotFoundError(run_id)
        return run

    def _require_document(self, *, workspace_id: UUID, document_id: UUID) -> Document:
        document = self._documents.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
            logger.warning(
                "run.require_document.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=document_id,
                ),
            )
            raise RunDocumentMissingError(f"Document {document_id} not found")
        return document

    def _require_documents(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[Document]:
        if not document_ids:
            return []

        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            Document.id.in_(document_ids),
        )
        result = self._session.execute(stmt)
        documents = list(result.scalars())
        found = {doc.id for doc in documents}
        missing = [document_id for document_id in document_ids if document_id not in found]
        if missing:
            logger.warning(
                "run.require_documents.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=str(missing[0]),
                    missing_count=len(missing),
                ),
            )
            raise RunDocumentMissingError(f"Document {missing[0]} not found")
        return documents

    def _storage_for(self, workspace_id: UUID) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base)

    def _resolve_configuration(self, configuration_id: UUID) -> Configuration:
        configuration = self._configs.get_by_id(configuration_id)
        if configuration is None:
            logger.warning(
                "run.config.resolve.not_found",
                extra=log_context(configuration_id=configuration_id),
            )
            raise ConfigurationNotFoundError(configuration_id)
        if configuration.status == ConfigurationStatus.ARCHIVED:
            logger.warning(
                "run.config.resolve.archived",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
        return configuration

    def _processing_paused(self, workspace_id: UUID) -> bool:
        workspace = self._workspaces.get_workspace(workspace_id)
        if workspace is None:
            return False
        return read_processing_paused(workspace.settings)

    def _resolve_workspace_configuration(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None,
    ) -> Configuration:
        if configuration_id is None:
            configuration = self._configs.get_active(workspace_id)
            if configuration is None:
                logger.warning(
                    "run.config.resolve.active_missing",
                    extra=log_context(workspace_id=workspace_id),
                )
                raise ConfigurationNotFoundError("active_configuration_not_found")
        else:
            configuration = self._configs.get(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
            )
            if configuration is None:
                logger.warning(
                    "run.config.resolve.not_found",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                    ),
                )
                raise ConfigurationNotFoundError(configuration_id)

        if configuration.status == ConfigurationStatus.ARCHIVED:
            logger.warning(
                "run.config.resolve.archived",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
        return configuration

    def _run_dir_for_run(self, *, workspace_id: UUID, run_id: UUID) -> Path:
        root = workspace_run_root(self._settings, workspace_id).resolve()
        candidate = (root / str(run_id)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:  # pragma: no cover - defensive guard
            logger.warning(
                "run.directory.escape_detected",
                extra=log_context(workspace_id=workspace_id, run_id=run_id, path=str(candidate)),
            )
            raise RunOutputMissingError("Requested path escapes runs directory") from None
        return candidate

    @staticmethod
    def _inspect_workbook(path: Path) -> list[RunOutputSheet]:
        with path.open("rb") as raw:
            workbook = openpyxl.load_workbook(
                raw,
                read_only=True,
                data_only=True,
                keep_links=False,
            )
            try:
                sheetnames = workbook.sheetnames
                active = workbook.active.title if sheetnames else None
                return [
                    RunOutputSheet(
                        name=title,
                        index=index,
                        kind="worksheet",
                        is_active=title == active,
                    )
                    for index, title in enumerate(sheetnames)
                ]
            finally:
                workbook.close()

    @staticmethod
    def _default_sheet_name(name: str | None) -> str:
        stem = Path(name or "Sheet").stem.strip() or "Sheet"
        return stem

    @staticmethod
    def _epoch_seconds(dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    @staticmethod
    def _merge_run_options(
        *,
        input_document_id: UUID,
        options: RunCreateOptionsBase | None,
    ) -> RunCreateOptions:
        payload = options.model_dump(exclude_none=True) if options else {}
        return RunCreateOptions(input_document_id=input_document_id, **payload)

    @staticmethod
    def _select_input_sheet_names(options: RunCreateOptions) -> list[str]:
        """Normalize requested sheet names into a unique, ordered list."""

        if getattr(options, "active_sheet_only", False):
            return []
        names: list[str] = []
        for name in getattr(options, "input_sheet_names", None) or []:
            if not isinstance(name, str):
                continue
            cleaned = name.strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
        return names

    @staticmethod
    def _select_input_sheet_name(options: RunCreateOptions) -> str | None:
        """Resolve the first selected sheet name from the run options, if any."""

        if getattr(options, "active_sheet_only", False):
            return None
        normalized = RunsService._select_input_sheet_names(options)
        return normalized[0] if normalized else None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
