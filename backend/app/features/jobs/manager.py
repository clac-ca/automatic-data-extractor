"""Asynchronous job queue manager."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.features.configs.activation_env import ActivationMetadataStore
from backend.app.features.configs.models import ConfigVersion
from backend.app.features.configs.repository import ConfigsRepository
from backend.app.features.configs.spec import ManifestLoader, ManifestV1
from backend.app.features.configs.storage import ConfigStorage
from backend.app.features.documents.repository import DocumentsRepository
from backend.app.features.documents.storage import DocumentStorage
from backend.app.shared.core.config import Settings
from backend.app.shared.core.time import utc_now

from .constants import SAFE_MODE_DISABLED_MESSAGE
from .exceptions import JobQueueFullError
from .models import Job, JobStatus
from .orchestrator import JobOrchestrator, RunResult
from .repository import JobsRepository
from .storage import JobStoragePaths, JobsStorage
from .types import ResolvedInput

logger = logging.getLogger(__name__)


class QueueReservation:
    """In-memory reservation for queue capacity."""

    __slots__ = ("_manager", "_active")

    def __init__(self, manager: "JobQueueManager") -> None:
        self._manager = manager
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    async def commit(self, job_id: str, *, attempt: int) -> None:
        """Place ``job_id`` on the queue using this reservation."""

        if not self._active:
            raise RuntimeError("Reservation has already been consumed")
        await self._manager._commit_reservation(job_id, attempt=attempt)
        self._active = False

    async def release(self) -> None:
        if not self._active:
            return
        await self._manager._release_reservation()
        self._active = False


class JobQueueManager:
    """Bounded in-memory queue with async workers executing jobs."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        if settings.storage_documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        self._settings = settings
        self._session_factory = session_factory
        self._queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=settings.queue_max_size)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._heartbeat_interval = settings.queue_heartbeat_interval
        self._stale_after = settings.queue_stale_after
        self._inflight: set[str] = set()
        self._reservation_lock = asyncio.Lock()
        self._reserved_slots = 0
        self._storage = JobsStorage(settings)
        self._document_storage = DocumentStorage(settings.storage_documents_dir)
        self._manifest_loader = ManifestLoader()
        self._config_storage = ConfigStorage(settings)
        self._activation_store = ActivationMetadataStore(self._config_storage)
        self._orchestrator = JobOrchestrator(
            self._storage,
            settings=settings,
            safe_mode_message=SAFE_MODE_DISABLED_MESSAGE,
            activation_store=self._activation_store,
        )

    @property
    def max_concurrency(self) -> int:
        return self._settings.queue_max_concurrency

    @property
    def max_size(self) -> int:
        return self._settings.queue_max_size

    def size(self) -> int:
        return self._queue.qsize()

    def metrics(self) -> dict[str, int]:
        return {
            "queue_size": self.size(),
            "max_size": self.max_size,
            "max_concurrency": self.max_concurrency,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for index in range(self._settings.queue_max_concurrency):
            task = asyncio.create_task(self._worker_loop(index + 1), name=f"job-worker-{index+1}")
            self._workers.append(task)
        await self.rehydrate()

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def try_reserve(self) -> QueueReservation:
        """Reserve a slot in the queue without enqueuing a job."""

        async with self._reservation_lock:
            if self.size() + self._reserved_slots >= self._settings.queue_max_size:
                raise JobQueueFullError(
                    max_size=self._settings.queue_max_size,
                    queue_size=self.size(),
                    max_concurrency=self._settings.queue_max_concurrency,
                )
            self._reserved_slots += 1
        return QueueReservation(self)

    async def enqueue(
        self,
        job_id: str,
        *,
        attempt: int,
        reservation: QueueReservation | None = None,
        force: bool = False,
    ) -> None:
        if job_id in self._inflight:
            return

        if reservation is not None:
            try:
                await reservation.commit(job_id, attempt=attempt)
            except Exception:
                await reservation.release()
                raise
        elif force:
            await self._put_job(job_id)
            self._record_enqueue_event(job_id=job_id, attempt=attempt)
        else:
            # No reservation and not forced indicates misuse.
            raise RuntimeError("Queue reservation required for enqueue")

    async def _commit_reservation(self, job_id: str, *, attempt: int) -> None:
        async with self._reservation_lock:
            if self._reserved_slots <= 0:
                raise RuntimeError("No reservation available to commit")
            self._reserved_slots -= 1
            try:
                self._put_job_nowait(job_id)
            except asyncio.QueueFull as exc:  # pragma: no cover - defensive
                self._reserved_slots += 1
                raise RuntimeError("Reserved slot unavailable") from exc

        self._record_enqueue_event(job_id=job_id, attempt=attempt)

    async def _release_reservation(self) -> None:
        async with self._reservation_lock:
            if self._reserved_slots > 0:
                self._reserved_slots -= 1

    def _put_job_nowait(self, job_id: str) -> None:
        self._inflight.add(job_id)
        self._queue.put_nowait(job_id)

    async def _put_job(self, job_id: str) -> None:
        self._inflight.add(job_id)
        await self._queue.put(job_id)

    def _record_enqueue_event(self, *, job_id: str, attempt: int) -> None:
        logs_path = self._storage.ensure_logs_path(job_id)
        self._storage.record_event(
            logs_path,
            event="enqueue",
            job_id=job_id,
            attempt=attempt,
            state=JobStatus.QUEUED.value,
            detail=self.metrics(),
        )


    async def rehydrate(self) -> None:
        async with self._session_factory() as session:
            jobs_repo = JobsRepository(session)
            queued = await jobs_repo.list_jobs_by_status(JobStatus.QUEUED)
            for job in queued:
                await self.enqueue(job.id, attempt=job.attempt, force=True)
            running = await jobs_repo.list_jobs_by_status(JobStatus.RUNNING)
            for job in running:
                await jobs_repo.requeue(job)
                await session.commit()
                await self.enqueue(job.id, attempt=job.attempt, force=True)
                logs_path = self._storage.ensure_logs_path(job.id)
                self._storage.record_event(
                    logs_path,
                    event="retry",
                    job_id=job.id,
                    attempt=job.attempt,
                    state=JobStatus.QUEUED.value,
                )

    async def _worker_loop(self, worker_id: int) -> None:
        logger.info("job worker %s started", worker_id)
        try:
            while True:
                job_id = await self._queue.get()
                if job_id is None:
                    self._queue.task_done()
                    break
                self._inflight.discard(job_id)
                try:
                    await self._process_job(job_id)
                except Exception:  # pragma: no cover - defensive logging
                    logger.exception("Unhandled error while processing job %s", job_id)
                finally:
                    self._queue.task_done()
        finally:
            logger.info("job worker %s stopped", worker_id)

    async def _process_job(self, job_id: str) -> None:
        async with self._session_factory() as session:
            job = await self._lock_job(session, job_id)
            if job is None:
                return
            config_version = await self._load_config(session, job)
            if config_version is None:
                await self._mark_failed(
                    session,
                    job,
                    error_message="Config version is not available",
                )
                return
            manifest = self._load_manifest(config_version)
            resolved_inputs = await self._resolve_inputs(session, job)
            trace_id = job.trace_id or job.id
            now = utc_now()
            repo = JobsRepository(session)
            await repo.update_status(
                job,
                status=JobStatus.RUNNING,
                started_at=now,
                last_heartbeat=now,
            )
            await session.commit()
            logs_path = self._storage.ensure_logs_path(job_id)
            self._storage.record_event(
                logs_path,
                event="start",
                job_id=job_id,
                attempt=job.attempt,
                state=JobStatus.RUNNING.value,
            )

        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat(job_id, heartbeat_stop))
        prepared_paths = self._storage.prepare(job_id)
        try:
            start_time = time.monotonic()
            run_result, paths = await self._orchestrator.run(
                job_id=job_id,
                attempt=job.attempt,
                config_version=config_version,
                manifest=manifest,
                trace_id=trace_id,
                input_files=resolved_inputs,
                timeout_seconds=max(1.0, manifest.engine.defaults.timeout_ms / 1000),
                paths=prepared_paths,
            )
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            await self._complete_job(
                job_id=job_id,
                attempt=job.attempt,
                run_result=run_result,
                paths=paths,
                elapsed_ms=elapsed_ms,
            )
        finally:
            heartbeat_stop.set()
            with suppress(Exception):
                await heartbeat_task
            self._storage.cleanup_inputs(prepared_paths)

    async def _complete_job(
        self,
        *,
        job_id: str,
        attempt: int,
        run_result: RunResult,
        paths: JobStoragePaths,
        elapsed_ms: int,
    ) -> None:
        async with self._session_factory() as session:
            repo = JobsRepository(session)
            job = await repo.load_job_by_id(job_id)
            if job is None:
                return
            if run_result.status == "succeeded" and run_result.artifact_path and run_result.output_path:
                await repo.update_status(
                    job,
                    status=JobStatus.SUCCEEDED,
                    completed_at=utc_now(),
                    artifact_uri=str(run_result.artifact_path),
                    output_uri=str(run_result.output_path),
                )
            else:
                error_message = run_result.error_message
                if not error_message and run_result.diagnostics:
                    first = run_result.diagnostics[0]
                    message = first.get("message")
                    code = first.get("code")
                    error_message = f"{code}: {message}" if code and message else message or code
                if run_result.timed_out:
                    error_message = error_message or "Worker timed out"
                await repo.update_status(
                    job,
                    status=JobStatus.FAILED,
                    completed_at=utc_now(),
                    error_message=error_message,
                )
            await repo.record_paths(
                job,
                logs_uri=str(paths.logs_path),
                run_request_uri=str(paths.request_path),
            )
            await session.commit()
            state = job.status
            detail: dict[str, str] | None = None
            if job.error_message:
                detail = {"error": job.error_message}
            self._storage.record_event(
                paths.logs_path,
                event="exit",
                job_id=job_id,
                attempt=attempt,
                state=state,
                duration_ms=elapsed_ms,
                detail=detail,
            )
            if state == JobStatus.FAILED.value:
                self._storage.record_event(
                    paths.logs_path,
                    event="error",
                    job_id=job_id,
                    attempt=attempt,
                    state=state,
                    detail=detail,
                )

    async def _lock_job(self, session: AsyncSession, job_id: str) -> Job | None:
        repo = JobsRepository(session)
        job = await repo.load_job_by_id(job_id)
        if job is None:
            return None
        if JobStatus(job.status) != JobStatus.QUEUED:
            return None
        # Single-process invariant: the queue manager is the sole mutator of queued jobs,
        # so we rely on that guarantee rather than explicit row-level locks.
        return job

    async def _load_config(self, session: AsyncSession, job: Job) -> ConfigVersion | None:
        if job.config_version is not None:
            return job.config_version
        configs = ConfigsRepository(session)
        return await configs.get_version_by_id(job.config_version_id)

    def _load_manifest(self, version: ConfigVersion) -> ManifestV1:
        return self._manifest_loader.load(version.manifest)

    async def _resolve_inputs(self, session: AsyncSession, job: Job) -> list[ResolvedInput]:
        documents = DocumentsRepository(session)
        resolved: list[ResolvedInput] = []
        for document_id in job.input_documents:
            document = await documents.get_document(
                workspace_id=job.workspace_id,
                document_id=document_id,
            )
            if document is None:
                raise RuntimeError(f"Document {document_id} is not available")
            source_path = self._document_storage.path_for(document.stored_uri)
            if not source_path.exists():
                raise RuntimeError(f"Document {document_id} content is missing from storage")
            filename = document.original_filename or f"{document_id}.bin"
            resolved.append(
                ResolvedInput(
                    document_id=document.document_id,
                    source_path=source_path,
                    filename=filename,
                    sha256=document.sha256,
                )
            )
        return resolved

    async def _heartbeat(self, job_id: str, stop_event: asyncio.Event) -> None:
        interval = max(1.0, self._heartbeat_interval.total_seconds())
        while True:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                async with self._session_factory() as session:
                    repo = JobsRepository(session)
                    job = await repo.load_job_by_id(job_id)
                    if job is None:
                        return
                    await repo.set_last_heartbeat(job, heartbeat_at=utc_now())
                    await session.commit()

    async def _mark_failed(
        self,
        session: AsyncSession,
        job: Job,
        *,
        error_message: str,
    ) -> None:
        repo = JobsRepository(session)
        await repo.update_status(
            job,
            status=JobStatus.FAILED,
            completed_at=utc_now(),
            error_message=error_message,
        )
        await session.commit()


__all__ = ["JobQueueManager", "QueueReservation"]
