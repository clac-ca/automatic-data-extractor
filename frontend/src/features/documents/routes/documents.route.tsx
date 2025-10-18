// documents.route.tsx — simple, beautiful, responsive, and stable (no layout shifts)

import { useCallback, useEffect, useMemo, useRef, useState, useId } from "react";
import type { ChangeEvent } from "react";
import clsx from "clsx";
import { useSearchParams } from "react-router-dom";

import { useWorkspaceContext } from "../../workspaces/context/WorkspaceContext";
import { useWorkspaceDocumentsQuery, type DocumentsStatusFilter } from "../api/queries";
import { downloadWorkspaceDocument } from "../api";
import { DocumentsTable } from "../components/DocumentsTable";
import { RunExtractionDrawer } from "../components/RunExtractionDrawer";
import { useUploadDocuments } from "../hooks/useUploadDocuments";
import { useDeleteDocuments } from "../hooks/useDeleteDocuments";
import { useDocumentJobsQuery } from "../../jobs/hooks/useJobs";
import type { DocumentRecord, DocumentStatus } from "../../../shared/types/documents";
import type { JobRecord, JobStatus } from "../../../shared/types/jobs";
import { Input } from "../../../ui/input";
import { Select } from "../../../ui/select";
import { Button } from "../../../ui/button";

/* -------------------------------------------------------------------------------------------------
 * Types & constants
 * -----------------------------------------------------------------------------------------------*/

type StatusOptionValue = "all" | DocumentStatus;

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const SORT_OPTIONS = ["-created_at", "created_at", "name", "-name", "status"] as const;
type SortOption = (typeof SORT_OPTIONS)[number];

function parseStatus(value: string | null): StatusOptionValue {
  const allowed = new Set<StatusOptionValue>(["all", "uploaded", "processing", "processed", "failed", "archived"]);
  return allowed.has((value as StatusOptionValue) ?? "all") ? ((value as StatusOptionValue) ?? "all") : "all";
}

function parseSort(value: string | null): SortOption {
  const allowed = new Set<string>(SORT_OPTIONS);
  return (allowed.has(value ?? "") ? (value as SortOption) : "-created_at") as SortOption;
}

/* -------------------------------------------------------------------------------------------------
 * Route
 * -----------------------------------------------------------------------------------------------*/

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();

  // URL-synced state
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState<StatusOptionValue>(parseStatus(searchParams.get("status")));
  const [sortOrder, setSortOrder] = useState<SortOption>(parseSort(searchParams.get("sort")));
  const [searchTerm, setSearchTerm] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm.trim());

  // File input + selection
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedIdsArray = useMemo(() => Array.from(selectedIdsSet), [selectedIdsSet]);
  const selectedCount = selectedIdsSet.size;

  // Operations
  const uploadDocuments = useUploadDocuments(workspace.id);
  const deleteDocuments = useDeleteDocuments(workspace.id);

  const [banner, setBanner] = useState<{ tone: "error"; message: string } | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [runDrawerDocument, setRunDrawerDocument] = useState<DocumentRecord | null>(null);

  const isUploading = uploadDocuments.isPending;
  const isDeleting = deleteDocuments.isPending;

  // Query
  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id, {
    status: statusFilter as DocumentsStatusFilter,
    search: debouncedSearch,
    sort: sortOrder,
  });
  const { refetch: refetchDocuments } = documentsQuery;
  const documents = documentsQuery.data?.items ?? [];

  /* -------------------------------- URL sync -------------------------------- */

  useEffect(() => {
    const s = new URLSearchParams();
    if (statusFilter !== "all") s.set("status", statusFilter);
    if (sortOrder !== "-created_at") s.set("sort", sortOrder);
    if (debouncedSearch) s.set("q", debouncedSearch);
    setSearchParams(s, { replace: true });
  }, [statusFilter, sortOrder, debouncedSearch, setSearchParams]);

  /* -------------------------------- Search debounce -------------------------------- */

  useEffect(() => {
    const h = window.setTimeout(() => setDebouncedSearch(searchTerm.trim()), 250);
    return () => window.clearTimeout(h);
  }, [searchTerm]);

  /* -------------------------------- Selection integrity -------------------------------- */

  useEffect(() => {
    setSelectedIds((current) => {
      if (current.size === 0) return current;
      const next = new Set<string>();
      const valid = new Set(documents.map((d) => d.document_id));
      let changed = false;
      for (const id of current) {
        if (valid.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [documents]);

  const firstSelectedDocument = useMemo(() => {
    for (const d of documents) if (selectedIdsSet.has(d.document_id)) return d;
    return null;
  }, [documents, selectedIdsSet]);

  /* -------------------------------- Keyboard shortcuts -------------------------------- */

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Upload
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "u") {
        e.preventDefault();
        fileInputRef.current?.click();
        return;
      }
      // Delete selection
      if ((e.key === "Delete" || e.key === "Backspace") && selectedCount > 0) {
        e.preventDefault();
        void handleDeleteSelected();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedCount]); // eslint-disable-line react-hooks/exhaustive-deps

  /* -------------------------------- Helpers -------------------------------- */

  const statusFormatter = useCallback(
    (status: DocumentStatus) => DOCUMENT_STATUS_LABELS[status] ?? status,
    [],
  );

  const renderJobStatus = useCallback(
    (documentItem: DocumentRecord) => (
      <DocumentJobStatus workspaceId={workspace.id} documentId={documentItem.document_id} />
    ),
    [workspace.id],
  );

  const handleOpenFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadFiles = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) return;
      setBanner(null);
      try {
        await uploadDocuments.mutateAsync({ files });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to upload documents.";
        setBanner({ tone: "error", message });
      }
    },
    [uploadDocuments],
  );

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    await handleUploadFiles(files);
    event.target.value = "";
  };

  const handleToggleDocument = (documentId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  };

  const handleToggleAll = () => {
    setSelectedIds((current) => {
      if (documents.length === 0) return new Set();
      const allIds = documents.map((doc) => doc.document_id);
      if (current.size === documents.length && allIds.every((id) => current.has(id))) return new Set();
      return new Set(allIds);
    });
  };

  const handleDeleteSelected = useCallback(async () => {
    const ids = selectedIdsArray;
    if (!ids.length) return;
    setBanner(null);
    try {
      await deleteDocuments.mutateAsync({ documentIds: ids });
      setSelectedIds(new Set());
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to delete documents.";
      setBanner({ tone: "error", message });
    }
  }, [deleteDocuments, selectedIdsArray]);

  const handleDeleteSingle = useCallback(
    async (document: DocumentRecord) => {
      setBanner(null);
      try {
        await deleteDocuments.mutateAsync({ documentIds: [document.document_id] });
        setSelectedIds((current) => {
          const next = new Set(current);
          next.delete(document.document_id);
          return next;
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to delete document.";
        setBanner({ tone: "error", message });
      }
    },
    [deleteDocuments],
  );

  const handleDownloadDocument = useCallback(
    async (document: DocumentRecord) => {
      try {
        setDownloadingId(document.document_id);
        const { blob, filename } = await downloadWorkspaceDocument(workspace.id, document.document_id);
        triggerBrowserDownload(blob, filename ?? document.name);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to download document.";
        setBanner({ tone: "error", message });
      } finally {
        setDownloadingId(null);
      }
    },
    [workspace.id],
  );

  const handleOpenRunDrawer = useCallback((document: DocumentRecord) => {
    setRunDrawerDocument(document);
  }, []);

  const handleRunSuccess = useCallback(
    (_job: JobRecord) => {
      void refetchDocuments();
    },
    [refetchDocuments],
  );

  const handleRunError = useCallback((message: string) => {
    setBanner({ tone: "error", message });
  }, []);

  const onResetFilters = () => {
    setSearchTerm("");
    setStatusFilter("all");
    setSortOrder("-created_at");
  };

  /* -------------------------------- Render -------------------------------- */

  const isDefaultFilters = statusFilter === "all" && sortOrder === "-created_at" && !debouncedSearch;

  return (
    <>
      {/* Global drop-anywhere overlay */}
      <DropAnywhereOverlay
        workspaceName={workspace.name ?? undefined}
        disabled={isUploading}
        onFiles={async (files) => {
          await handleUploadFiles(files);
        }}
      />

      <div className="space-y-4">
        {/* Page header — balanced + calm */}
        <header className="rounded-xl border border-slate-200 bg-white/95 px-4 py-4 sm:px-5">
          <h1 className="text-lg font-semibold text-slate-900 sm:text-xl">Documents</h1>
          <p className="mt-1 text-sm text-slate-600">
            Manage uploads and runs across {workspace.name ?? "this workspace"}.
          </p>
        </header>

        {/* Hidden file input (paired with toolbar Upload) */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Toolbar — minimal, elegant, responsive, and stable */}
        <DocumentsToolbar
          search={searchTerm}
          onSearch={setSearchTerm}
          status={statusFilter}
          onStatus={setStatusFilter}
          sort={sortOrder}
          onSort={setSortOrder}
          onReset={onResetFilters}
          isFetching={documentsQuery.isFetching}
          isDefault={isDefaultFilters}
          onUploadClick={handleOpenFilePicker}
          uploadDisabled={isUploading}
        />

        {/* Inline error banner (non-blocking) */}
        {banner ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
            {banner.message}
          </div>
        ) : null}

        {/* Content panel; allow horizontal scroll on tiny screens */}
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 sm:p-4">
          {documentsQuery.isLoading ? (
            <SkeletonList />
          ) : documentsQuery.isError ? (
            <p className="text-rose-600">Failed to load documents.</p>
          ) : documents.length === 0 ? (
            <EmptyState onUploadClick={handleOpenFilePicker} />
          ) : (
            <DocumentsTable
              documents={documents}
              selectedIds={selectedIdsSet}
              onToggleDocument={handleToggleDocument}
              onToggleAll={handleToggleAll}
              disableSelection={documentsQuery.isFetching || isDeleting || uploadDocuments.isPending}
              disableRowActions={deleteDocuments.isPending}
              formatStatusLabel={statusFormatter}
              onDeleteDocument={handleDeleteSingle}
              onDownloadDocument={handleDownloadDocument}
              onRunDocument={handleOpenRunDrawer}
              downloadingId={downloadingId}
              renderJobStatus={renderJobStatus}
            />
          )}
        </div>
      </div>

      {/* Bottom bulk action bar */}
      <BulkBar
        count={selectedCount}
        onClear={() => setSelectedIds(new Set())}
        onRun={() => {
          if (firstSelectedDocument) handleOpenRunDrawer(firstSelectedDocument);
        }}
        onDelete={handleDeleteSelected}
        busy={isDeleting}
      />

      {/* Run drawer */}
      <RunExtractionDrawer
        open={Boolean(runDrawerDocument)}
        workspaceId={workspace.id}
        documentRecord={runDrawerDocument}
        onClose={() => setRunDrawerDocument(null)}
        onRunSuccess={handleRunSuccess}
        onRunError={handleRunError}
      />
    </>
  );
}

/* -------------------------------------------------------------------------------------------------
 * UI pieces
 * -----------------------------------------------------------------------------------------------*/

/** Global drag & drop overlay (appears only during drag) */
function DropAnywhereOverlay({
  onFiles,
  disabled,
  workspaceName,
}: {
  onFiles: (files: File[]) => void | Promise<void>;
  disabled?: boolean;
  workspaceName?: string;
}) {
  const [active, setActive] = useState(false);
  const counterRef = useRef(0);

  useEffect(() => {
    if (disabled) return;

    const onDragEnter = (e: DragEvent) => {
      if (!e.dataTransfer || ![...e.dataTransfer.types].includes("Files")) return;
      counterRef.current += 1;
      setActive(true);
    };
    const onDragOver = (e: DragEvent) => {
      if (!active) return;
      e.preventDefault(); // allow drop
    };
    const onDragLeave = () => {
      counterRef.current = Math.max(0, counterRef.current - 1);
      if (counterRef.current === 0) setActive(false);
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      setActive(false);
      counterRef.current = 0;
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length) void onFiles(files);
    };

    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [active, disabled, onFiles]);

  return (
    <div
      aria-hidden={!active}
      className={clsx(
        "pointer-events-none fixed inset-0 z-[60] transition",
        active ? "opacity-100" : "opacity-0"
      )}
    >
      <div className="absolute inset-0 bg-slate-900/25 backdrop-blur-[2px]" />
      <div className="absolute inset-0 flex items-center justify-center p-6">
        <div className="pointer-events-none rounded-2xl border border-white/70 bg-white/90 px-6 py-5 shadow-2xl">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow">
              <svg viewBox="0 0 24 24" className="h-5 w-5 text-slate-700" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div className="text-center sm:text-left">
              <p className="text-base font-semibold text-slate-900">Drop to upload</p>
              <p className="text-sm text-slate-600">
                Files will upload to <span className="font-medium">{workspaceName ?? "this workspace"}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Toolbar — clean & compact (search, status, sort, reset, indicator, upload). 
    Mobile stacks; ≥sm uses fixed footprints to avoid shifts. */
function DocumentsToolbar({
  search,
  onSearch,
  status,
  onStatus,
  sort,
  onSort,
  onReset,
  isFetching,
  isDefault,
  onUploadClick,
  uploadDisabled,
}: {
  search: string;
  onSearch: (v: string) => void;
  status: StatusOptionValue;
  onStatus: (v: StatusOptionValue) => void;
  sort: SortOption;
  onSort: (v: SortOption) => void;
  onReset: () => void;
  isFetching?: boolean;
  isDefault: boolean;
  onUploadClick: () => void;
  uploadDisabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const searchId = useId();

  // Quick shortcuts: "/" or Cmd/Ctrl+K to focus search; Esc to clear
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if (key === "/" && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        return;
      }
      if (key === "escape" && document.activeElement === inputRef.current && search) {
        onSearch("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [search, onSearch]);

  return (
    <div
      className="rounded-xl border border-slate-200 bg-white/95 px-3 py-3 sm:px-4"
      role="region"
      aria-label="Documents filters"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr,auto,auto,auto] sm:items-center sm:gap-3">
        {/* Search */}
        <div className="relative">
          <Input
            id={searchId}
            ref={inputRef as any}
            type="search"
            placeholder="Search documents (⌘K or /)"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full"
            aria-label="Search documents"
          />
          {search ? (
            <button
              type="button"
              onClick={() => onSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-xs text-slate-500 hover:text-slate-800"
              title="Clear (Esc)"
              aria-label="Clear search"
            >
              ×
            </button>
          ) : null}
        </div>

        {/* Status (clean dropdown to keep UI minimal) */}
        <Select
          value={status}
          onChange={(e) => onStatus(e.target.value as StatusOptionValue)}
          className="w-full sm:w-[170px]"
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="processing">{DOCUMENT_STATUS_LABELS.processing}</option>
          <option value="failed">{DOCUMENT_STATUS_LABELS.failed}</option>
          <option value="uploaded">{DOCUMENT_STATUS_LABELS.uploaded}</option>
          <option value="processed">{DOCUMENT_STATUS_LABELS.processed}</option>
          <option value="archived">{DOCUMENT_STATUS_LABELS.archived}</option>
        </Select>

        {/* Sort */}
        <Select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortOption)}
          className="w-full sm:w-[170px]"
          aria-label="Sort documents"
        >
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="name">Name A–Z</option>
          <option value="-name">Name Z–A</option>
          <option value="status">Status</option>
        </Select>

        {/* Actions cluster (fixed footprints ≥sm) */}
        <div className="flex items-center gap-2 sm:justify-end">
          <button
            type="button"
            onClick={onReset}
            disabled={isDefault}
            className={clsx(
              "rounded text-sm",
              isDefault ? "cursor-default text-slate-300" : "text-slate-600 underline underline-offset-4 hover:text-slate-900"
            )}
            title="Reset filters"
          >
            Reset
          </button>

          {/* Reserved indicator slot on ≥sm to avoid shifts */}
          <div className="hidden sm:block sm:w-[86px]">
            <SyncIndicator isFetching={Boolean(isFetching)} />
          </div>

          {/* Upload fills width on mobile; fixed on ≥sm */}
          <Button className="w-full sm:w-[104px]" onClick={onUploadClick} disabled={uploadDisabled} isLoading={uploadDisabled}>
            Upload
          </Button>
        </div>
      </div>
    </div>
  );
}

/** Tiny "Updating…" indicator (uses opacity so width never changes) */
function SyncIndicator({ isFetching }: { isFetching: boolean }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center justify-end gap-1 text-xs text-slate-500",
        isFetching ? "opacity-100" : "opacity-0"
      )}
      role="status"
      aria-live="polite"
    >
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
      Updating…
    </span>
  );
}

/** Simple skeleton placeholder while loading */
function SkeletonList() {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="h-4 w-4 rounded bg-slate-100" />
          <div className="h-4 flex-1 rounded bg-slate-100" />
          <div className="h-4 w-24 rounded bg-slate-100" />
          <div className="h-4 w-40 rounded bg-slate-100" />
          <div className="h-8 w-40 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

/** Bottom bulk action bar (appears only when there is a selection) */
function BulkBar({
  count,
  onClear,
  onRun,
  onDelete,
  busy,
}: {
  count: number;
  onClear: () => void;
  onRun: () => void;
  onDelete: () => void;
  busy?: boolean;
}) {
  if (count === 0) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-7xl px-2 pb-2 sm:px-4 sm:pb-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 text-sm text-slate-700 shadow-lg backdrop-blur">
        <span className="mr-2"><strong>{count}</strong> selected</span>
        <Button variant="ghost" size="sm" onClick={onClear}>Clear</Button>
        <Button size="sm" onClick={onRun} disabled={busy}>Run extraction</Button>
        <Button size="sm" variant="danger" onClick={onDelete} disabled={busy} isLoading={busy}>Delete</Button>
      </div>
    </div>
  );
}

/** Empty state for when there are no documents */
function EmptyState({ onUploadClick }: { onUploadClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-50">
        <svg className="h-6 w-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M12 16V4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-base font-semibold text-slate-900">No documents yet</p>
      <p className="max-w-md text-sm text-slate-600">Tap Upload or drag files anywhere in the window.</p>
      <Button onClick={onUploadClick} className="w-full sm:w-auto">Upload</Button>
    </div>
  );
}

/* -------------------------------------------------------------------------------------------------
 * Status / formatting helpers
 * -----------------------------------------------------------------------------------------------*/

function DocumentJobStatus({ workspaceId, documentId }: { workspaceId: string; documentId: string }) {
  const jobsQuery = useDocumentJobsQuery(workspaceId, documentId, { limit: 3 });

  if (jobsQuery.isLoading) return <span className="text-xs text-slate-400">Loading runs…</span>;

  if (jobsQuery.isError) {
    return (
      <span className="text-xs text-rose-600">
        {jobsQuery.error instanceof Error ? jobsQuery.error.message : "Unable to load runs."}
      </span>
    );
  }

  const jobs = jobsQuery.data ?? [];
  if (jobs.length === 0) return <span className="text-xs text-slate-400">No runs yet</span>;

  const latestJob = jobs[0];
  const remaining = jobs.length - 1;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={clsx(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
          jobStatusBadgeClass(latestJob.status),
        )}
      >
        {formatJobStatus(latestJob.status)}
        <span className="ml-1 font-normal text-slate-500">{formatRelativeTime(latestJob.updated_at)}</span>
      </span>
      {remaining > 0 ? <span className="text-[11px] text-slate-400">+{remaining} more</span> : null}
    </div>
  );
}

function jobStatusBadgeClass(status: JobStatus) {
  switch (status) {
    case "succeeded":
      return "bg-success-100 text-success-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "running":
      return "bg-brand-100 text-brand-700";
    default:
      return "bg-slate-200 text-slate-700";
  }
}

function formatJobStatus(status: JobStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const diffMs = date.getTime() - Date.now();
  const diffSeconds = Math.round(diffMs / 1000);
  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return relativeTimeFormatter.format(diffSeconds, "second");
  const diffMinutes = Math.round(diffSeconds / 60);
  const absMinutes = Math.abs(diffMinutes);
  if (absMinutes < 60) return relativeTimeFormatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) return relativeTimeFormatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) return relativeTimeFormatter.format(diffDays, "day");
  const diffMonths = Math.round(diffDays / 30);
  if (Math.abs(diffMonths) < 12) return relativeTimeFormatter.format(diffMonths, "month");
  const diffYears = Math.round(diffDays / 365);
  return relativeTimeFormatter.format(diffYears, "year");
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
