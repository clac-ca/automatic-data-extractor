// Workspace documents index route — one-file screen with inline helpers.

import { useCallback, useEffect, useMemo, useRef, useState, useId } from "react";
import type { ChangeEvent, ReactNode } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { useSearchParams } from "react-router";

import { useWorkspaceContext } from "@features/workspaces/context/WorkspaceContext";
import { useDocumentsQuery } from "@features/documents/hooks/useDocumentsQuery";
import type { DocumentsStatusFilter } from "@features/documents/api";
import { downloadWorkspaceDocument as downloadDocument } from "@features/documents/api";
import { useUploadDocuments } from "@features/documents/hooks/useUploadDocuments";
import { useDeleteDocuments } from "@features/documents/hooks/useDeleteDocuments";
import { useDocumentRunPreferences } from "@features/documents/hooks/useDocumentRunPreferences";
import { useConfigurationsQuery } from "@features/configurations/hooks/useConfigurationsQuery";
import { useDocumentJobsQuery, useSubmitJobMutation } from "@features/jobs/hooks/useJobsQuery";
import type { DocumentRecord, DocumentStatus } from "@shared/types/documents";
import type { JobRecord, JobStatus } from "@shared/types/jobs";
import { Alert } from "@ui/alert";
import { Input } from "@ui/input";
import { Select } from "@ui/select";
import { Button } from "@ui/button";

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

export default function WorkspaceDocumentsRoute() {
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
  const documentsQuery = useDocumentsQuery(workspace.id, {
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
        const { blob, filename } = await downloadDocument(workspace.id, document.document_id);
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

const uploadedFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

interface DocumentsTableProps {
  readonly documents: readonly DocumentRecord[];
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleDocument: (documentId: string) => void;
  readonly onToggleAll: () => void;
  readonly disableSelection?: boolean;
  readonly disableRowActions?: boolean;
  readonly formatStatusLabel?: (status: DocumentRecord["status"]) => string;
  readonly onDeleteDocument?: (document: DocumentRecord) => void;
  readonly onDownloadDocument?: (document: DocumentRecord) => void;
  readonly onRunDocument?: (document: DocumentRecord) => void;
  readonly downloadingId?: string | null;
  readonly renderJobStatus?: (document: DocumentRecord) => ReactNode;
}

function DocumentsTable({
  documents,
  selectedIds,
  onToggleDocument,
  onToggleAll,
  disableSelection = false,
  disableRowActions = false,
  formatStatusLabel,
  onDeleteDocument,
  onDownloadDocument,
  onRunDocument,
  downloadingId = null,
  renderJobStatus,
}: DocumentsTableProps) {
  const headerCheckboxRef = useRef<HTMLInputElement | null>(null);

  const { allSelected, someSelected } = useMemo(() => {
    if (documents.length === 0) {
      return { allSelected: false, someSelected: false };
    }
    const selectedCount = documents.reduce(
      (count, document) => (selectedIds.has(document.document_id) ? count + 1 : count),
      0,
    );
    return {
      allSelected: selectedCount === documents.length,
      someSelected: selectedCount > 0 && selectedCount < documents.length,
    };
  }, [documents, selectedIds]);

  useEffect(() => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full table-auto border-separate border-spacing-0 text-sm text-slate-700">
        <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500 shadow-sm">
          <tr>
            <th scope="col" className="w-10 px-3 py-2">
              <input
                ref={headerCheckboxRef}
                type="checkbox"
                className="h-4 w-4 rounded border border-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={disableSelection || documents.length === 0}
              />
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Name
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Status
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              Uploaded
            </th>
            <th scope="col" className="px-3 py-2 text-right">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const isSelected = selectedIds.has(document.document_id);
            return (
              <tr
                key={document.document_id}
                className={clsx(
                  "border-b border-slate-200 last:border-b-0 transition hover:bg-slate-50",
                  isSelected ? "bg-brand-50" : "bg-white",
                )}
              >
                <td className="px-3 py-2 align-middle">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border border-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    checked={isSelected}
                    onChange={() => onToggleDocument(document.document_id)}
                    disabled={disableSelection}
                  />
                </td>
                <td className="px-3 py-2 align-middle">
                  <div className="flex flex-col gap-1">
                    <span className="truncate font-semibold text-slate-900" title={document.name}>
                      {document.name}
                    </span>
                    <span className="flex items-center gap-2 text-xs text-slate-500">
                      {formatFileDescription(document)}
                    </span>
                    {renderJobStatus ? (
                      <div className="text-xs text-slate-500">{renderJobStatus(document)}</div>
                    ) : null}
                  </div>
                </td>
                <td className="px-3 py-2 align-middle">
                  <span className={clsx("rounded-full px-2 py-1 text-[11px] font-semibold uppercase", statusBadgeClass(document.status))}>
                    {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
                  </span>
                </td>
                <td className="px-3 py-2 align-middle">
                  <time
                    dateTime={document.created_at}
                    className="block truncate text-xs text-slate-600"
                    title={uploadedFormatter.format(new Date(document.created_at))}
                  >
                    {formatUploadedAt(document)}
                  </time>
                </td>
                <td className="px-3 py-2 align-middle text-right">
                  <DocumentActionsMenu
                    document={document}
                    onDownload={onDownloadDocument}
                    onDelete={onDeleteDocument}
                    onRun={onRunDocument}
                    disabled={disableRowActions}
                    downloading={downloadingId === document.document_id}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function formatFileDescription(document: DocumentRecord) {
  const parts: string[] = [];
  if (document.content_type) {
    parts.push(humanizeContentType(document.content_type));
  }
  if (typeof document.byte_size === "number" && document.byte_size >= 0) {
    parts.push(formatFileSize(document.byte_size));
  }
  return parts.join(" • ") || "Unknown type";
}

function humanizeContentType(contentType: string) {
  const mapping: Record<string, string> = {
    "application/pdf": "PDF document",
    "text/csv": "CSV file",
    "text/tab-separated-values": "TSV file",
    "application/vnd.ms-excel": "Excel spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel spreadsheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12": "Excel macro spreadsheet",
  };
  return mapping[contentType] ?? contentType;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const formatted = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${formatted} ${units[unitIndex]}`;
}

function statusBadgeClass(status: DocumentRecord["status"]) {
  switch (status) {
    case "processed":
      return "bg-success-100 text-success-700";
    case "processing":
      return "bg-warning-100 text-warning-700";
    case "failed":
      return "bg-danger-100 text-danger-700";
    case "archived":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function formatUploadedAt(document: DocumentRecord) {
  return uploadedFormatter.format(new Date(document.created_at));
}

interface DocumentActionsMenuProps {
  readonly document: DocumentRecord;
  readonly onDownload?: (document: DocumentRecord) => void;
  readonly onDelete?: (document: DocumentRecord) => void;
  readonly onRun?: (document: DocumentRecord) => void;
  readonly disabled?: boolean;
  readonly downloading?: boolean;
}

function DocumentActionsMenu({
  document,
  onDownload,
  onDelete,
  onRun,
  disabled = false,
  downloading = false,
}: DocumentActionsMenuProps) {
  return (
    <div className="inline-flex items-center gap-2">
      <Button
        type="button"
        size="sm"
        variant="primary"
        onClick={() => onRun?.(document)}
        disabled={disabled || !onRun}
      >
        Run
      </Button>
      <button
        type="button"
        onClick={() => onDownload?.(document)}
        className={clsx(
          "flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-200 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
          downloading && "opacity-60",
        )}
        disabled={disabled || downloading}
      >
        Download
        {downloading ? (
          <span className="inline-flex h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
        ) : null}
      </button>
      <button
        type="button"
        onClick={() => onDelete?.(document)}
        className="flex items-center gap-1 rounded-lg border border-danger-200 px-3 py-1.5 text-xs font-semibold text-danger-600 transition hover:border-danger-300 hover:text-danger-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        disabled={disabled}
      >
        Delete
      </button>
    </div>
  );
}

interface RunExtractionDrawerProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
}

function RunExtractionDrawer({
  open,
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
}: RunExtractionDrawerProps) {
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (open) {
      previouslyFocusedElementRef.current =
        window.document.activeElement instanceof HTMLElement ? window.document.activeElement : null;
    } else {
      previouslyFocusedElementRef.current?.focus();
      previouslyFocusedElementRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open || typeof window === "undefined") {
      return;
    }
    const originalOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  if (typeof window === "undefined" || !open || !documentRecord) {
    return null;
  }

  return createPortal(
    <RunExtractionDrawerContent
      workspaceId={workspaceId}
      documentRecord={documentRecord}
      onClose={onClose}
      onRunSuccess={onRunSuccess}
      onRunError={onRunError}
    />,
    window.document.body,
  );
}

interface DrawerContentProps {
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
}

function RunExtractionDrawerContent({
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
}: DrawerContentProps) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  const configurationsQuery = useConfigurationsQuery(workspaceId);
  const submitJob = useSubmitJobMutation(workspaceId);
  const { preferences, setPreferences } = useDocumentRunPreferences(
    workspaceId,
    documentRecord.document_id,
  );

  const configurations = configurationsQuery.data ?? [];
  const activeConfiguration = useMemo(
    () => configurations.find((configuration) => configuration.is_active) ?? null,
    [configurations],
  );

  const [selectedConfigurationId, setSelectedConfigurationId] = useState<string | "">(
    preferences.configurationId ?? activeConfiguration?.configuration_id ?? "",
  );

  useEffect(() => {
    setSelectedConfigurationId(
      preferences.configurationId ?? activeConfiguration?.configuration_id ?? "",
    );
  }, [preferences.configurationId, activeConfiguration?.configuration_id]);

  const selectedConfiguration = configurations.find(
    (configuration) => configuration.configuration_id === selectedConfigurationId,
  );

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    const focusable = getFocusableElements(dialog);
    (focusable[0] ?? dialog).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusableElements = getFocusableElements(dialog);
      if (focusableElements.length === 0) {
        event.preventDefault();
        return;
      }
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = window.document.activeElement;

      if (event.shiftKey) {
        if (!dialog.contains(activeElement) || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
        return;
      }

      if (activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    dialog.addEventListener("keydown", handleKeyDown);
    return () => {
      dialog.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  const hasConfigurations = configurations.length > 0;

  const handleSubmit = () => {
    if (!selectedConfiguration) {
      setErrorMessage("Select a configuration before running the extractor.");
      return;
    }
    setErrorMessage(null);
    submitJob.mutate(
      {
        input_document_id: documentRecord.document_id,
        configuration_id: selectedConfiguration.configuration_id,
        configuration_version: selectedConfiguration.version,
      },
      {
        onSuccess: (job) => {
          setPreferences({
            configurationId: selectedConfiguration.configuration_id,
            configurationVersion: selectedConfiguration.version,
          });
          onRunSuccess?.(job);
          onClose();
        },
        onError: (error) => {
          const message = (
            error instanceof Error ? error.message : "Unable to submit extraction job."
          );
          setErrorMessage(message);
          onRunError?.(message);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="flex-1 bg-slate-900/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="relative flex h-full w-[min(28rem,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">Run extraction</h2>
            <p id={descriptionId} className="text-xs text-slate-500">Prepare and submit a processing job.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitJob.isPending}>
            Close
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-sm text-slate-600">
          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Document
            </p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-800" title={documentRecord.name}>
                {documentRecord.name}
              </p>
              <p className="text-xs text-slate-500">Uploaded {new Date(documentRecord.created_at).toLocaleString()}</p>
              {documentRecord.last_run_at ? (
                <p className="text-xs text-slate-500">
                  Last run {new Date(documentRecord.last_run_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Configuration
            </p>
            {configurationsQuery.isLoading ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Loading configurations…
              </div>
            ) : configurationsQuery.isError ? (
              <Alert tone="danger">
                Unable to load configurations. {" "}
                {configurationsQuery.error instanceof Error
                  ? configurationsQuery.error.message
                  : "Try again later."}
              </Alert>
            ) : hasConfigurations ? (
              <Select
                value={selectedConfigurationId}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedConfigurationId(value);
                  if (value) {
                    const target = configurations.find(
                      (configuration) => configuration.configuration_id === value,
                    );
                    if (target) {
                      setPreferences({
                        configurationId: target.configuration_id,
                        configurationVersion: target.version,
                      });
                    }
                  }
                }}
                disabled={submitJob.isPending}
              >
                <option value="">Select configuration</option>
                {configurations.map((configuration) => (
                  <option key={configuration.configuration_id} value={configuration.configuration_id}>
                    {configuration.title} (v{configuration.version})
                    {configuration.is_active ? " • Active" : ""}
                  </option>
                ))}
              </Select>
            ) : (
              <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
            )}
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Advanced options
            </p>
            <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Sheet selection and advanced flags will appear here once the processor supports them.
            </p>
          </section>

          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitJob.isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            isLoading={submitJob.isPending}
            disabled={!hasConfigurations || submitJob.isPending}
          >
            Run extraction
          </Button>
        </footer>
      </aside>
    </div>
  );
}


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

function getFocusableElements(container: HTMLElement) {
  const selectors = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];
  return Array.from(container.querySelectorAll<HTMLElement>(selectors.join(','))).filter(
    (element) => !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true',
  );
}
