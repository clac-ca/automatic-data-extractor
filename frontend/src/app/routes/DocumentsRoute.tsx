import clsx from "clsx";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";

import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useDocuments } from "../../features/documents/hooks/useDocuments";
import { useUploadDocuments } from "../../features/documents/hooks/useUploadDocuments";
import { useDeleteDocuments } from "../../features/documents/hooks/useDeleteDocuments";
import { downloadWorkspaceDocument } from "../../features/documents/api";
import type { DocumentRecord, DocumentStatus } from "../../shared/types/documents";
import { Alert, Button, Input, Select } from "../../ui";
import { DocumentsTable, DocumentActionsMenu } from "./documents/DocumentsTable";

type StatusOption = "all" | DocumentStatus;
type ViewMode = "table" | "grid";

interface ToastState {
  readonly tone: "success" | "info" | "danger";
  readonly message: string;
}

const STATUS_OPTIONS: StatusOption[] = ["all", "uploaded", "processing", "processed", "failed", "archived"];

const STATUS_LABELS: Record<StatusOption, string> = {
  all: "All statuses",
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
  archived: "Archived",
};

const SORT_OPTIONS = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "name", label: "Name A–Z" },
  { value: "-name", label: "Name Z–A" },
  { value: "status", label: "Status" },
];

const TOAST_STYLE: Record<ToastState["tone"], string> = {
  success: "bg-success-600",
  info: "bg-brand-600",
  danger: "bg-danger-600",
};

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const [statusFilter, setStatusFilter] = useState<StatusOption>("all");
  const [sortOrder, setSortOrder] = useState<string>(SORT_OPTIONS[0]!.value);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => setSearchQuery(searchInput.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => {
      setToast(null);
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const documentsQuery = useDocuments(workspace.id, {
    status: statusFilter,
    search: searchQuery,
    sort: sortOrder,
  });
  const uploadDocuments = useUploadDocuments(workspace.id);
  const deleteDocuments = useDeleteDocuments(workspace.id);

  const documents = documentsQuery.data?.items ?? [];
  const selectedIdsSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  useEffect(() => {
    setSelectedIds((previous) => {
      if (previous.length === 0) {
        return previous;
      }
      const availableIds = new Set(documents.map((document) => document.document_id));
      const next = previous.filter((id) => availableIds.has(id));
      return next.length === previous.length ? previous : next;
    });
  }, [documents]);

  const showToast = useCallback((tone: ToastState["tone"], message: string) => {
    setToast({ tone, message });
  }, []);

  const clearFileInput = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const processFiles = useCallback(
    (files: readonly File[]) => {
      const accepted = Array.from(files);
      if (accepted.length === 0) {
        return;
      }
      uploadDocuments.mutate(
        { files: accepted },
        {
          onSuccess: () => {
            showToast("success", accepted.length === 1 ? "Document uploaded." : `${accepted.length} documents uploaded.`);
            clearFileInput();
          },
          onError: (error: unknown) => {
            const message = error instanceof Error ? error.message : "Unable to upload documents.";
            showToast("danger", message);
            clearFileInput();
          },
        },
      );
    },
    [clearFileInput, showToast, uploadDocuments],
  );

  const handleStatusChange = useCallback((event: ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(event.target.value as StatusOption);
    setSelectedIds([]);
  }, []);

  const handleSortChange = useCallback((event: ChangeEvent<HTMLSelectElement>) => {
    setSortOrder(event.target.value);
  }, []);

  const handleSearchChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setSearchInput(event.target.value);
  }, []);

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      processFiles(Array.from(event.target.files ?? []));
    },
    [processFiles],
  );

  const handlePickFiles = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleToggleDocument = useCallback((documentId: string) => {
    setSelectedIds((previous) =>
      previous.includes(documentId) ? previous.filter((id) => id !== documentId) : [...previous, documentId],
    );
  }, []);

  const handleToggleAll = useCallback(() => {
    setSelectedIds((previous) => {
      if (documents.length === 0) {
        return [];
      }
      const allIds = documents.map((document) => document.document_id);
      const allSelected = previous.length === documents.length && previous.every((id) => allIds.includes(id));
      return allSelected ? [] : allIds;
    });
  }, [documents]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds([]);
  }, []);

  const handleDeleteSelected = useCallback(() => {
    if (selectedIds.length === 0) {
      return;
    }
    const documentIds = [...selectedIds];
    deleteDocuments.mutate(
      { documentIds },
      {
        onSuccess: () => {
          showToast(
            "success",
            documentIds.length === 1 ? "Document deleted." : `${documentIds.length} documents deleted.`,
          );
          setSelectedIds([]);
        },
        onError: (error: unknown) => {
          const message =
            error instanceof Error ? error.message : "Unable to delete the selected documents.";
          showToast("danger", message);
        },
      },
    );
  }, [deleteDocuments, selectedIds, showToast]);

  const handleDeleteSingle = useCallback(
    (document: DocumentRecord) => {
      deleteDocuments.mutate(
        { documentIds: [document.document_id] },
        {
          onSuccess: () => {
            showToast("success", "Document deleted.");
            setSelectedIds((previous) => previous.filter((id) => id !== document.document_id));
          },
          onError: (error: unknown) => {
            const message =
              error instanceof Error ? error.message : "Unable to delete this document.";
            showToast("danger", message);
          },
        },
      );
    },
    [deleteDocuments, showToast],
  );

  const handleDownloadDocument = useCallback(
    async (document: DocumentRecord) => {
      try {
        setDownloadingId(document.document_id);
        const { blob, filename } = await downloadWorkspaceDocument(workspace.id, document.document_id);
        triggerBrowserDownload(blob, filename ?? document.name);
        showToast("success", "Download started.");
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to download this document.";
        showToast("danger", message);
      } finally {
        setDownloadingId(null);
      }
    },
    [showToast, workspace.id],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!isDragActive) {
      setIsDragActive(true);
    }
  }, [isDragActive]);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node)) {
      return;
    }
    setIsDragActive(false);
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragActive(false);
      const files = event.dataTransfer?.files;
      if (!files) {
        return;
      }
      processFiles(Array.from(files));
    },
    [processFiles],
  );

  const isLoading = documentsQuery.isLoading && !documentsQuery.isFetched;
  const isRefreshing = documentsQuery.isRefetching || documentsQuery.isFetching;
  const loadError = documentsQuery.error;
  const hasNext = documentsQuery.data?.has_next ?? false;
  const selectedCount = selectedIds.length;

  const statusFormatter = useCallback(
    (status: DocumentStatus) => STATUS_LABELS[status] ?? status,
    [],
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8 lg:py-8">
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 top-20 z-50 flex justify-center px-4">
        {toast ? (
          <div
            role="status"
            className={clsx(
              "pointer-events-auto flex items-center gap-3 rounded-full px-4 py-2 text-sm font-medium text-white shadow-lg",
              TOAST_STYLE[toast.tone],
            )}
          >
            {toast.message}
            <button
              type="button"
              className="rounded-full border border-white/40 px-2 py-0.5 text-xs font-semibold hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              onClick={() => setToast(null)}
            >
              Dismiss
            </button>
          </div>
        ) : null}
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-6 p-6">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold text-slate-900">Documents</h1>
              <p className="mt-1 text-sm text-slate-600">
                Track uploads across {workspace.name ?? "this workspace"}, refine by status, and take action without
                leaving the table.
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.pdf,.tsv,.xls,.xlsx,.xlsm,.xlsb"
                multiple
                className="hidden"
                onChange={handleFileChange}
              />
              <Button onClick={handlePickFiles} isLoading={uploadDocuments.isPending}>
                Upload documents
              </Button>
              <span className="text-[11px] uppercase tracking-wide text-slate-500">
                PDF, CSV, TSV, XLS, XLSX, XLSM, XLSB
              </span>
            </div>
          </header>

          {loadError ? (
            <Alert tone="danger" heading="Unable to load documents">
              {loadError instanceof Error ? loadError.message : "Something went wrong while fetching documents."}
            </Alert>
          ) : null}

          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <Input
              placeholder="Search documents"
              value={searchInput}
              onChange={handleSearchChange}
              className="w-full max-w-sm"
            />
            <Select
              value={statusFilter}
              onChange={handleStatusChange}
              disabled={documentsQuery.isLoading || documentsQuery.isFetching}
              className="w-full max-w-[180px]"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {STATUS_LABELS[option]}
                </option>
              ))}
            </Select>
            <Select value={sortOrder} onChange={handleSortChange} className="w-full max-w-[180px]">
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <div className="ml-auto flex items-center gap-1 rounded-lg border border-slate-300 bg-white p-1">
              <Button
                size="sm"
                variant={viewMode === "table" ? "primary" : "ghost"}
                onClick={() => setViewMode("table")}
              >
                Table
              </Button>
              <Button
                size="sm"
                variant={viewMode === "grid" ? "primary" : "ghost"}
                onClick={() => setViewMode("grid")}
                title="Grid view (experimental)"
              >
                Grid
              </Button>
            </div>
          </div>

          <div
            className={clsx(
              "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition",
              isDragActive ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-100",
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handlePickFiles}
          >
            <p className="text-sm font-medium text-slate-700">Drag & drop files here</p>
            <p className="text-xs text-slate-500">or click to open the file picker</p>
          </div>

          {selectedCount > 0 ? (
            <div className="sticky top-4 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 px-4 py-2 shadow">
              <span className="text-sm font-medium text-slate-700">
                {selectedCount} selected
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleClearSelection}
                disabled={deleteDocuments.isPending}
              >
                Clear
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={handleDeleteSelected}
                disabled={deleteDocuments.isPending}
                isLoading={deleteDocuments.isPending}
              >
                Delete
              </Button>
            </div>
          ) : null}

          <div className="flex flex-col gap-3">
            {isLoading ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
                Loading documents…
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-300 px-6 py-12 text-center text-sm text-slate-600">
                <p className="text-lg font-semibold text-slate-800">No documents yet</p>
                <p className="text-sm text-slate-500">
                  Upload files to populate this workspace. Drag and drop or use the upload button above.
                </p>
                <Button onClick={handlePickFiles}>Upload documents</Button>
              </div>
            ) : viewMode === "table" ? (
              <DocumentsTable
                documents={documents}
                selectedIds={selectedIdsSet}
                onToggleDocument={handleToggleDocument}
                onToggleAll={handleToggleAll}
                disableSelection={deleteDocuments.isPending}
                disableRowActions={deleteDocuments.isPending}
                formatStatusLabel={statusFormatter}
                onDeleteDocument={handleDeleteSingle}
                onDownloadDocument={handleDownloadDocument}
                downloadingId={downloadingId}
              />
            ) : (
              <DocumentsGrid
                documents={documents}
                selectedIds={selectedIdsSet}
                onToggleDocument={handleToggleDocument}
                disableSelection={deleteDocuments.isPending}
                onDeleteDocument={handleDeleteSingle}
                onDownloadDocument={handleDownloadDocument}
                formatStatusLabel={statusFormatter}
                downloadingId={downloadingId}
              />
            )}

            {isRefreshing && documents.length > 0 ? (
              <p className="text-xs text-slate-500">Refreshing…</p>
            ) : null}
            {hasNext ? (
              <p className="text-xs text-slate-500">
                Showing the first {documents.length} documents. Pagination will return later.
              </p>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}

interface DocumentsGridProps {
  readonly documents: readonly DocumentRecord[];
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleDocument: (documentId: string) => void;
  readonly disableSelection?: boolean;
  readonly onDeleteDocument?: (document: DocumentRecord) => void;
  readonly onDownloadDocument?: (document: DocumentRecord) => void;
  readonly formatStatusLabel?: (status: DocumentStatus) => string;
  readonly downloadingId?: string | null;
}

function DocumentsGrid({
  documents,
  selectedIds,
  onToggleDocument,
  disableSelection = false,
  onDeleteDocument,
  onDownloadDocument,
  formatStatusLabel,
  downloadingId = null,
}: DocumentsGridProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {documents.map((document) => {
        const isSelected = selectedIds.has(document.document_id);
        return (
          <article
            key={document.document_id}
            className={clsx(
              "relative flex flex-col gap-3 rounded-xl border border-slate-200 p-4 transition hover:border-brand-300 hover:shadow-sm",
              isSelected ? "ring-2 ring-brand-400" : "bg-white",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border border-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  checked={isSelected}
                  onChange={() => onToggleDocument(document.document_id)}
                  disabled={disableSelection}
                />
                <span className="truncate">{document.name}</span>
              </label>
              <DocumentActionsMenu
                document={document}
                onDownload={onDownloadDocument}
                onDelete={onDeleteDocument}
                disabled={disableSelection}
                downloading={downloadingId === document.document_id}
              />
            </div>
            <p className="text-xs text-slate-500">{formatFileSummary(document)}</p>
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span
                className={clsx(
                  "rounded-full px-2 py-1 text-[11px] font-semibold uppercase",
                  statusBadgeClass(document.status),
                )}
              >
                {formatStatusLabel ? formatStatusLabel(document.status) : document.status}
              </span>
              <time dateTime={document.created_at}>{formatUploadedAt(document)}</time>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function formatFileSummary(document: DocumentRecord) {
  const parts: string[] = [];
  if (document.content_type) {
    parts.push(humanizeContentType(document.content_type));
  }
  if (typeof document.byte_size === "number") {
    parts.push(formatFileSize(document.byte_size));
  }
  return parts.join(" • ") || "Unknown file type";
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

function formatUploadedAt(document: DocumentRecord) {
  const date = new Date(document.created_at);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return uploadedFormatter.format(date);
}

const uploadedFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

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

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(url);
}
