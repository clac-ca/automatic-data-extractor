import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, ReactNode } from "react";
import clsx from "clsx";

import { useSession } from "../../features/auth/context/SessionContext";
import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import { useUploadDocumentsMutation } from "../../features/documents/hooks/useUploadDocumentsMutation";
import { useDeleteDocumentsMutation } from "../../features/documents/hooks/useDeleteDocumentsMutation";
import { downloadWorkspaceDocument } from "../../features/documents/api";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import type { WorkspaceDocumentSummary } from "../../shared/types/documents";
import type { SessionUser } from "../../shared/types/auth";
import { PageState } from "../components/PageState";
import { Alert, Button } from "../../ui";
import { trackEvent } from "../../shared/telemetry/events";
import { ApiError } from "../../shared/api/client";

const OWNER_FILTER_OPTIONS = [
  { value: "mine", label: "My Documents" },
  { value: "all", label: "All Documents" },
] as const;

const SUPPORTED_FILE_EXTENSIONS = [".pdf", ".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".xlsb"] as const;
const SUPPORTED_FILE_EXTENSION_SET = new Set(
  SUPPORTED_FILE_EXTENSIONS.map((value) => value.toLowerCase()),
);
const SUPPORTED_FILE_TYPES_LABEL = "PDF, CSV, TSV, XLS, XLSX, XLSM, XLSB";

interface FeedbackState {
  readonly tone: "info" | "success" | "warning" | "danger";
  readonly message: string;
}

type OwnerFilter = (typeof OWNER_FILTER_OPTIONS)[number]["value"];

type DocumentStatus = "inbox" | "processing" | "completed" | "failed" | "archived";

interface DocumentItem {
  readonly id: string;
  readonly name: string;
  readonly status: DocumentStatus;
  readonly source: string;
  readonly tags: readonly string[];
  readonly uploadedAt: Date;
  readonly byteSize: number;
  readonly contentType: string | null;
  readonly uploaderName: string;
  readonly uploaderId: string | null;
  readonly uploaderEmail: string | null;
  readonly lastRunLabel: string;
  readonly lastRunAt: Date | null;
  readonly metadata: Record<string, unknown>;
  readonly summary: WorkspaceDocumentSummary;
}

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const { user: currentUser } = useSession();

  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id);
  const uploadDocuments = useUploadDocumentsMutation(workspace.id);
  const deleteDocuments = useDeleteDocumentsMutation(workspace.id);
  const { openInspector } = useWorkspaceChrome();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepthRef = useRef(0);

  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>("mine");
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!currentUser?.user_id && ownerFilter === "mine") {
      setOwnerFilter("all");
    }
  }, [currentUser?.user_id, ownerFilter]);

  useEffect(() => {
    if (!feedback || typeof window === "undefined") {
      return;
    }
    const timer = window.setTimeout(() => setFeedback(null), 6000);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  const documents = useMemo<readonly DocumentItem[]>(
    () => (documentsQuery.data ?? []).map((document) => buildDocumentItem(document)),
    [documentsQuery.data],
  );

  const visibleDocuments = useMemo(() => {
    const list = ownerFilter === "mine"
      ? documents.filter((document) => belongsToCurrentUser(document, currentUser))
      : documents;

    return [...list].sort(sortDocumentsByUploadedAt);
  }, [documents, ownerFilter, currentUser]);

  const hasDocuments = documents.length > 0;
  const hasVisibleDocuments = visibleDocuments.length > 0;

  const handleOwnerFilterChange = useCallback(
    (value: OwnerFilter) => {
      setOwnerFilter(value);
      trackDocumentsEvent("filter_owner", workspace.id, { owner: value });
    },
    [workspace.id],
  );

  const handleUploadButtonClick = useCallback(() => {
    setFeedback(null);
    fileInputRef.current?.click();
    trackDocumentsEvent("start_upload", workspace.id);
  }, [workspace.id]);

  const handleFilesSelected = useCallback(
    async (files: readonly File[]) => {
      if (!files.length) {
        return;
      }

      const { accepted, rejected } = partitionSupportedFiles(files);
      if (accepted.length === 0) {
        setFeedback({
          tone: "warning",
          message: `No supported files detected. Supported types: ${SUPPORTED_FILE_TYPES_LABEL}.`,
        });
        return;
      }

      setFeedback(null);

      try {
        const uploaded = await uploadDocuments.mutateAsync({ files: accepted });
        const count = uploaded.length;
        const label = count === 1 ? accepted[0]?.name ?? "Document" : `${count} documents`;
        const skipped = rejected.length
          ? ` ${rejected.length} file${rejected.length === 1 ? "" : "s"} skipped (unsupported type).`
          : "";
        setFeedback({
          tone: "success",
          message: `${label} uploaded.${skipped}`,
        });
        trackDocumentsEvent(count === 1 ? "upload" : "bulk_upload", workspace.id, {
          documentId: uploaded[0]?.id,
          count,
        });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to upload documents. Try again."),
        });
      }
    },
    [uploadDocuments, workspace.id],
  );

  const handleFileInputChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files ? Array.from(event.target.files) : [];
      event.target.value = "";
      if (!files.length) {
        return;
      }
      await handleFilesSelected(files);
    },
    [handleFilesSelected],
  );

  const handleDragEnter = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current += 1;
    if (!isDragging) {
      setIsDragging(true);
    }
  }, [isDragging]);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  const handleDrop = useCallback(
    async (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      dragDepthRef.current = 0;
      const files = extractFilesFromDataTransfer(event.dataTransfer);
      if (files.length === 0) {
        return;
      }
      await handleFilesSelected(files);
    },
    [handleFilesSelected],
  );

  const handleDownload = useCallback(
    async (document: DocumentItem) => {
      try {
        setFeedback(null);
        setDownloadingId(document.id);
        const { blob, filename } = await downloadWorkspaceDocument(workspace.id, document.id);
        triggerBrowserDownload(blob, filename);
        trackDocumentsEvent("download", workspace.id, { documentId: document.id });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to download document. Try again."),
        });
      } finally {
        setDownloadingId(null);
      }
    },
    [workspace.id],
  );

  const handleDelete = useCallback(
    async (document: DocumentItem) => {
      if (typeof window !== "undefined") {
        const confirmed = window.confirm(`Delete ${document.name}? This action cannot be undone.`);
        if (!confirmed) {
          return;
        }
      }

      try {
        setFeedback(null);
        setDeletingId(document.id);
        await deleteDocuments.mutateAsync([document.id]);
        setFeedback({ tone: "success", message: "Document deleted." });
        trackDocumentsEvent("delete", workspace.id, { documentId: document.id });
      } catch (error) {
        setFeedback({
          tone: "danger",
          message: resolveApiErrorMessage(error, "Unable to delete document. Try again."),
        });
      } finally {
        setDeletingId(null);
      }
    },
    [deleteDocuments, workspace.id],
  );

  const handleInspect = useCallback(
    (document: DocumentItem) => {
      openInspector({
        title: document.name,
        content: <DocumentDetails document={document} />,
      });
      trackDocumentsEvent("view_details", workspace.id, { documentId: document.id });
    },
    [openInspector, workspace.id],
  );

  if (documentsQuery.isLoading) {
    return (
      <PageState
        title="Loading documents"
        description="Fetching workspace documents."
        variant="loading"
      />
    );
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <section className="flex h-full flex-col gap-4">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={SUPPORTED_FILE_EXTENSIONS.join(",")}
        className="hidden"
        onChange={handleFileInputChange}
      />

      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <div
        role="region"
        aria-label="Workspace documents"
        className={clsx(
          "flex flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft transition",
          isDragging ? "border-dashed border-brand-400 ring-4 ring-brand-100" : "hover:border-slate-300",
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between">
          <OwnerFilterSelect value={ownerFilter} onChange={handleOwnerFilterChange} />
          <div className="flex flex-wrap items-center justify-end gap-3 text-sm text-slate-500">
            <span className="hidden sm:inline">Drag and drop files here or</span>
            <Button onClick={handleUploadButtonClick} isLoading={uploadDocuments.isPending}>
              Upload documents
            </Button>
          </div>
        </div>

        <div className="relative flex-1 overflow-auto p-4">
          {hasVisibleDocuments ? (
            <div className="grid grid-cols-1 gap-3">
              {visibleDocuments.map((document) => (
                <DocumentRow
                  key={document.id}
                  document={document}
                  onInspect={handleInspect}
                  onDownload={handleDownload}
                  onDelete={handleDelete}
                  isDownloading={downloadingId === document.id}
                  isDeleting={deletingId === document.id}
                />
              ))}
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
              <p>
                {ownerFilter === "mine"
                  ? "No documents uploaded by you yet."
                  : hasDocuments
                    ? "No documents match this filter."
                    : "No documents uploaded yet."}
              </p>
              {ownerFilter === "mine" && hasDocuments ? (
                <Button variant="secondary" size="sm" onClick={() => setOwnerFilter("all")}>View all documents</Button>
              ) : (
                <Button onClick={handleUploadButtonClick} isLoading={uploadDocuments.isPending} size="sm">
                  Upload documents
                </Button>
              )}
            </div>
          )}

          {isDragging ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl border-4 border-dashed border-brand-300 bg-brand-50/80 text-sm font-semibold text-brand-700">
              Drop files to upload
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

interface OwnerFilterSelectProps {
  readonly value: OwnerFilter;
  readonly onChange: (value: OwnerFilter) => void;
}

function OwnerFilterSelect({ value, onChange }: OwnerFilterSelectProps) {
  return (
    <label className="flex flex-col text-xs font-semibold uppercase tracking-wide text-slate-500 sm:flex-row sm:items-center">
      <span>Showing</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as OwnerFilter)}
        className="mt-2 w-48 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white sm:ml-3 sm:mt-0"
      >
        {OWNER_FILTER_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface DocumentRowProps {
  readonly document: DocumentItem;
  readonly onInspect: (document: DocumentItem) => void;
  readonly onDownload: (document: DocumentItem) => void;
  readonly onDelete: (document: DocumentItem) => void;
  readonly isDownloading: boolean;
  readonly isDeleting: boolean;
}

function DocumentRow({
  document,
  onInspect,
  onDownload,
  onDelete,
  isDownloading,
  isDeleting,
}: DocumentRowProps) {
  return (
    <article className="group flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-soft transition hover:border-brand-300 hover:shadow-md">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onInspect(document)}
          className="max-w-full text-left text-base font-semibold text-slate-900 transition hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          <span className="line-clamp-2 break-words">{document.name}</span>
        </button>
        <StatusBadge status={document.status} />
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-600">
        <span className="flex items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
            {document.contentType ?? "Unknown type"}
          </span>
          <span>{formatFileSize(document.byteSize)}</span>
        </span>
        <span>
          Uploaded {formatRelativeTime(document.uploadedAt)} by {document.uploaderName}
        </span>
        <span>Source: {document.source}</span>
        <span>Last run: {document.lastRunLabel}</span>
      </div>

      {document.tags.length ? (
        <div className="flex flex-wrap gap-2">
          {document.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => onInspect(document)}>
          View details
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onDownload(document)} isLoading={isDownloading}>
          Download
        </Button>
        <Button variant="danger" size="sm" onClick={() => onDelete(document)} isLoading={isDeleting}>
          Delete
        </Button>
      </div>
    </article>
  );
}

interface DocumentDetailsProps {
  readonly document: DocumentItem;
}

function DocumentDetails({ document }: DocumentDetailsProps) {
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-1 gap-2 text-sm text-slate-700">
        <DetailField label="Name">{document.name}</DetailField>
        <DetailField label="Status">
          <StatusBadge status={document.status} />
        </DetailField>
        <DetailField label="Content type">{document.contentType ?? "Unknown"}</DetailField>
        <DetailField label="File size">{formatFileSize(document.byteSize)}</DetailField>
        <DetailField label="Uploaded">
          {formatDateTime(document.uploadedAt)}
        </DetailField>
        <DetailField label="Uploaded by">{document.uploaderName}</DetailField>
        {document.lastRunAt ? (
          <DetailField label="Last run">
            {document.lastRunLabel} on {formatDateTime(document.lastRunAt)}
          </DetailField>
        ) : (
          <DetailField label="Last run">{document.lastRunLabel}</DetailField>
        )}
        <DetailField label="Source">{document.source}</DetailField>
      </section>

      {document.tags.length ? (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {document.tags.map((tag) => (
              <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
                {tag}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
        {Object.keys(document.metadata).length === 0 ? (
          <p className="text-sm text-slate-500">No metadata attached.</p>
        ) : (
          <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900/90 p-3 text-xs text-slate-100">
            {JSON.stringify(document.metadata, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}

interface DetailFieldProps {
  readonly label: string;
  readonly children: ReactNode;
}

function DetailField({ label, children }: DetailFieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <span>{children}</span>
    </div>
  );
}

const STATUS_LABELS: Record<DocumentStatus, string> = {
  inbox: "Inbox",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  archived: "Archived",
};

const STATUS_BADGE_STYLE: Record<DocumentStatus, string> = {
  inbox: "bg-indigo-100 text-indigo-700",
  processing: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-danger-100 text-danger-700",
  archived: "bg-slate-200 text-slate-700",
};

interface StatusBadgeProps {
  readonly status: DocumentStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        STATUS_BADGE_STYLE[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

function belongsToCurrentUser(document: DocumentItem, user: SessionUser | null): boolean {
  if (!user) {
    return false;
  }

  if (document.uploaderId && user.user_id && document.uploaderId === user.user_id) {
    return true;
  }

  const normalizedName = (user.display_name ?? "").trim().toLowerCase();
  if (normalizedName && document.uploaderName.trim().toLowerCase() === normalizedName) {
    return true;
  }

  const normalizedEmail = user.email.trim().toLowerCase();
  if (document.uploaderEmail && document.uploaderEmail.trim().toLowerCase() === normalizedEmail) {
    return true;
  }

  return false;
}

function sortDocumentsByUploadedAt(a: DocumentItem, b: DocumentItem) {
  const delta = b.uploadedAt.getTime() - a.uploadedAt.getTime();
  if (delta !== 0) {
    return delta;
  }
  return a.name.localeCompare(b.name);
}

function buildDocumentItem(document: WorkspaceDocumentSummary): DocumentItem {
  const metadata = document.metadata ?? {};
  const status = extractStatus(metadata);
  const source = extractString(metadata, ["source", "ingestSource"], "Manual upload");
  const tags = extractTags(metadata);
  const uploadedAt = safeDate(document.createdAt ?? document.updatedAt ?? new Date().toISOString());
  const { name, id, email } = extractUploader(metadata);
  const lastRun = extractLastRun(metadata);

  return {
    id: document.id,
    name: document.name,
    status,
    source,
    tags,
    uploadedAt,
    byteSize: document.byteSize,
    contentType: document.contentType,
    uploaderName: name,
    uploaderId: id,
    uploaderEmail: email,
    lastRunLabel: lastRun.result,
    lastRunAt: lastRun.timestamp,
    metadata,
    summary: document,
  };
}

function extractStatus(metadata: Record<string, unknown>): DocumentStatus {
  if (metadata.archived === true) {
    return "archived";
  }

  const rawStatus = extractString(metadata, ["status", "state"], "");
  switch (rawStatus.toLowerCase()) {
    case "inbox":
      return "inbox";
    case "processing":
    case "running":
      return "processing";
    case "failed":
    case "error":
      return "failed";
    case "archived":
      return "archived";
    case "completed":
    case "succeeded":
    case "success":
      return "completed";
    default:
      break;
  }

  if (metadata.processing === true) {
    return "processing";
  }
  if (metadata.failed === true) {
    return "failed";
  }

  return "completed";
}

function extractString(
  metadata: Record<string, unknown>,
  keys: readonly string[],
  fallback: string,
): string {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return fallback;
}

function extractTags(metadata: Record<string, unknown>): readonly string[] {
  const raw = metadata.tags ?? metadata.labels;
  if (Array.isArray(raw)) {
    return raw
      .map((value) => (typeof value === "string" ? value.trim() : String(value)))
      .filter((value) => value.length > 0);
  }
  if (typeof raw === "string" && raw.trim().length > 0) {
    return raw
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
  }
  return [];
}

function extractUploader(metadata: Record<string, unknown>) {
  const name = extractString(
    metadata,
    ["uploader", "uploadedBy", "createdBy", "owner", "ownerName"],
    "Unknown",
  );
  const id = extractOptionalString(metadata, [
    "uploaderId",
    "uploader_id",
    "uploadedById",
    "uploaded_by_id",
    "createdById",
    "created_by_id",
    "ownerId",
    "owner_id",
  ]);
  const email = extractOptionalString(metadata, [
    "uploaderEmail",
    "uploadedByEmail",
    "createdByEmail",
    "ownerEmail",
    "email",
  ]);
  return { name, id, email };
}

function extractOptionalString(metadata: Record<string, unknown>, keys: readonly string[]) {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return null;
}

function extractLastRun(metadata: Record<string, unknown>) {
  const raw = metadata.lastRun ?? metadata.last_run ?? metadata.jobStatus ?? metadata.latestJob;
  if (raw && typeof raw === "object") {
    const maybeTimestamp = extractOptionalString(raw as Record<string, unknown>, [
      "completedAt",
      "completed_at",
      "timestamp",
      "updatedAt",
      "updated_at",
    ]);
    const timestamp = maybeTimestamp ? safeDate(maybeTimestamp) : null;
    const result = extractString(raw as Record<string, unknown>, ["result", "status", "state"], "Not started");
    return {
      result: capitalize(result),
      timestamp,
    };
  }

  const status = extractOptionalString(metadata, ["lastRunStatus", "jobStatus", "status"]);
  if (status) {
    return { result: capitalize(status), timestamp: null };
  }

  return { result: "Not started", timestamp: null };
}

function capitalize(value: string) {
  if (value.length === 0) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function safeDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return new Date();
  }
  return date;
}

function partitionSupportedFiles(files: readonly File[]) {
  const accepted: File[] = [];
  const rejected: File[] = [];
  for (const file of files) {
    const extension = getExtension(file.name);
    if (extension && SUPPORTED_FILE_EXTENSION_SET.has(extension)) {
      accepted.push(file);
    } else {
      rejected.push(file);
    }
  }
  return { accepted, rejected };
}

function getExtension(filename: string) {
  const index = filename.lastIndexOf(".");
  if (index === -1) {
    return "";
  }
  return filename.slice(index).toLowerCase();
}

function extractFilesFromDataTransfer(dataTransfer: DataTransfer | null) {
  if (!dataTransfer) {
    return [];
  }

  const files: File[] = [];
  if (dataTransfer.files && dataTransfer.files.length > 0) {
    for (const file of Array.from(dataTransfer.files)) {
      files.push(file);
    }
    return files;
  }

  if (dataTransfer.items) {
    for (const item of Array.from(dataTransfer.items)) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }
  }

  return files;
}

function resolveApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.problem?.detail ?? error.message ?? fallback;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function formatDateTime(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatRelativeTime(date: Date) {
  const now = Date.now();
  const value = date.getTime();
  const deltaSeconds = Math.round((value - now) / 1000);

  const divisions: readonly [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.34524, "week"],
    [12, "month"],
    [Number.POSITIVE_INFINITY, "year"],
  ];

  let remainder = deltaSeconds;
  let unit: Intl.RelativeTimeFormatUnit = "second";

  for (const [amount, nextUnit] of divisions) {
    if (Math.abs(remainder) < amount) {
      unit = nextUnit;
      break;
    }
    remainder /= amount;
    unit = nextUnit;
  }

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  return formatter.format(Math.round(remainder), unit);
}

function trackDocumentsEvent(
  action: string,
  workspaceId: string,
  payload: Record<string, unknown> = {},
) {
  trackEvent({
    name: `documents.${action}`,
    payload: { workspaceId, ...payload },
  });
}
