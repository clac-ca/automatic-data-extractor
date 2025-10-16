import { ApiError } from "../../../shared/api/client";
import type { SessionUser } from "../../../shared/types/auth";
import type { WorkspaceDocumentSummary } from "../../../shared/types/documents";
import { trackEvent } from "../../../shared/telemetry/events";

export type OwnerFilterValue = "mine" | "all";

export type DocumentStatus = "inbox" | "processing" | "completed" | "failed" | "archived";

export type StatusFilterValue = "all" | DocumentStatus;

export type SortColumn = "name" | "status" | "source" | "uploadedAt" | "lastRunAt" | "byteSize";

export type SortDirection = "asc" | "desc";

export interface SortState {
  readonly column: SortColumn;
  readonly direction: SortDirection;
}

export interface DocumentRow {
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
}

export const OWNER_FILTER_OPTIONS = [
  { value: "mine", label: "My Documents" },
  { value: "all", label: "All Documents" },
] as const;

export const STATUS_FILTER_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "inbox", label: "Inbox" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "archived", label: "Archived" },
] as const;

export const SUPPORTED_FILE_EXTENSIONS = [
  ".pdf",
  ".csv",
  ".tsv",
  ".xls",
  ".xlsx",
  ".xlsm",
  ".xlsb",
] as const;

export const SUPPORTED_FILE_TYPES_LABEL = "PDF, CSV, TSV, XLS, XLSX, XLSM, XLSB";

export const DEFAULT_SORT_STATE: SortState = { column: "uploadedAt", direction: "desc" };

const STATUS_SORT_ORDER: Record<DocumentStatus, number> = {
  processing: 0,
  inbox: 1,
  failed: 2,
  completed: 3,
  archived: 4,
};

const ALLOWED_EXTENSIONS = new Set(SUPPORTED_FILE_EXTENSIONS.map((value) => value.toLowerCase()));

interface DocumentFilters {
  readonly owner: OwnerFilterValue;
  readonly status: StatusFilterValue;
  readonly search: string;
  readonly currentUser: SessionUser | null;
}

export function toDocumentRows(documents: readonly WorkspaceDocumentSummary[] | undefined): DocumentRow[] {
  if (!documents) {
    return [];
  }

  return documents.map((document) => {
    const metadata = document.metadata ?? {};
    const uploader = resolveUploader(metadata);
    const lastRun = resolveLastRun(metadata);

    return {
      id: document.id,
      name: document.name,
      status: resolveStatus(metadata),
      source: resolveSource(metadata),
      tags: resolveTags(metadata),
      uploadedAt: resolveUploadedAt(document),
      byteSize: document.byteSize,
      contentType: document.contentType,
      uploaderName: uploader.name,
      uploaderId: uploader.id,
      uploaderEmail: uploader.email,
      lastRunLabel: lastRun.label,
      lastRunAt: lastRun.completedAt,
      metadata,
    } satisfies DocumentRow;
  });
}

export function applyDocumentFilters(rows: readonly DocumentRow[], filters: DocumentFilters) {
  const term = filters.search.trim().toLowerCase();

  return rows.filter((row) => {
    if (filters.owner === "mine" && !isOwnedByUser(row, filters.currentUser)) {
      return false;
    }

    if (filters.status !== "all" && row.status !== filters.status) {
      return false;
    }

    if (!term) {
      return true;
    }

    return [row.name, row.source, row.uploaderName, row.lastRunLabel, ...row.tags]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(term));
  });
}

export function sortDocumentRows(rows: readonly DocumentRow[], sortState: SortState) {
  const { column, direction } = sortState;
  const directionMultiplier = direction === "asc" ? 1 : -1;

  const compare = (a: DocumentRow, b: DocumentRow) => {
    switch (column) {
      case "name":
        return a.name.localeCompare(b.name);
      case "status":
        return STATUS_SORT_ORDER[a.status] - STATUS_SORT_ORDER[b.status] || a.name.localeCompare(b.name);
      case "source":
        return a.source.localeCompare(b.source);
      case "uploadedAt":
        return a.uploadedAt.getTime() - b.uploadedAt.getTime();
      case "lastRunAt": {
        const timeA = a.lastRunAt?.getTime() ?? 0;
        const timeB = b.lastRunAt?.getTime() ?? 0;
        if (timeA === timeB) {
          return a.name.localeCompare(b.name);
        }
        return timeA - timeB;
      }
      case "byteSize":
        return a.byteSize - b.byteSize;
      default:
        return 0;
    }
  };

  return [...rows].sort((a, b) => compare(a, b) * directionMultiplier);
}

export function toggleSort(column: SortColumn, current: SortState): SortState {
  if (current.column !== column) {
    return {
      column,
      direction: column === "uploadedAt" || column === "lastRunAt" || column === "byteSize" ? "desc" : "asc",
    };
  }

  return { column, direction: current.direction === "asc" ? "desc" : "asc" };
}

export function splitSupportedFiles(files: readonly File[]) {
  const accepted: File[] = [];
  const rejected: File[] = [];

  for (const file of files) {
    const extension = getFileExtension(file.name);
    if (extension && ALLOWED_EXTENSIONS.has(extension)) {
      accepted.push(file);
    } else {
      rejected.push(file);
    }
  }

  return { accepted, rejected };
}

export function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function formatDateTime(value: Date) {
  return dateTimeFormatter.format(value);
}

export function formatRelativeTime(value: Date) {
  const diffMs = value.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / 60_000);
  const absMinutes = Math.abs(diffMinutes);

  if (absMinutes < 60) {
    return relativeTimeFormatter.format(diffMinutes, "minute");
  }

  const diffHours = Math.round(diffMinutes / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) {
    return relativeTimeFormatter.format(diffHours, "hour");
  }

  const diffDays = Math.round(diffHours / 24);
  return relativeTimeFormatter.format(diffDays, "day");
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${integerFormatter.format(bytes)} B`;
  }

  const units = ["KB", "MB", "GB", "TB"] as const;
  let value = bytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const formatter = value >= 10 || unitIndex === 0 ? integerFormatter : decimalFormatter;
  return `${formatter.format(value)} ${units[unitIndex]}`;
}

export function formatStatusLabel(status: DocumentStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function resolveApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.problem?.detail ?? error.message ?? fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function trackDocumentsEvent(action: string, workspaceId: string, payload: Record<string, unknown> = {}) {
  trackEvent({
    name: `documents.${action}`,
    payload: { workspaceId, ...payload },
  });
}

function isOwnedByUser(row: DocumentRow, user: SessionUser | null) {
  if (!user) {
    return false;
  }

  if (row.uploaderId && user.user_id && row.uploaderId === user.user_id) {
    return true;
  }

  const normalizedName = (user.display_name ?? "").trim().toLowerCase();
  if (normalizedName && row.uploaderName.trim().toLowerCase() === normalizedName) {
    return true;
  }

  const normalizedEmail = user.email.trim().toLowerCase();
  if (row.uploaderEmail && row.uploaderEmail.trim().toLowerCase() === normalizedEmail) {
    return true;
  }

  return false;
}

function resolveStatus(metadata: Record<string, unknown>): DocumentStatus {
  if (metadata.archived === true) {
    return "archived";
  }

  const rawStatus = readString(metadata, ["status", "state"]).toLowerCase();
  switch (rawStatus) {
    case "processing":
    case "running":
      return "processing";
    case "failed":
    case "error":
      return "failed";
    case "completed":
    case "done":
      return "completed";
    case "archived":
      return "archived";
    case "inbox":
      return "inbox";
    default:
      return metadata.completed === true ? "completed" : "inbox";
  }
}

function resolveSource(metadata: Record<string, unknown>) {
  return readString(metadata, ["source", "ingestSource"], "Manual upload");
}

function resolveTags(metadata: Record<string, unknown>) {
  const raw = metadata.tags;
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .filter((value): value is string => typeof value === "string" && value.trim().length > 0)
    .map((value) => value.trim());
}

function resolveUploadedAt(document: WorkspaceDocumentSummary) {
  const timestamp = document.updatedAt ?? document.createdAt;
  return parseDateOrNow(timestamp);
}

function resolveUploader(metadata: Record<string, unknown>) {
  const uploader = metadata.uploader;
  if (uploader && typeof uploader === "object" && !Array.isArray(uploader)) {
    const record = uploader as Record<string, unknown>;
    return {
      id: typeof record.id === "string" && record.id.trim() ? record.id : null,
      name: readString(record, ["name"], "Unknown"),
      email: readString(record, ["email"], "") || null,
    };
  }

  return {
    id: null,
    name: readString(metadata, ["uploadedBy", "createdBy"], "Unknown"),
    email: readString(metadata, ["uploadedByEmail", "createdByEmail"], "") || null,
  };
}

function resolveLastRun(metadata: Record<string, unknown>) {
  const job = metadata.lastRun;
  if (job && typeof job === "object" && !Array.isArray(job)) {
    const record = job as Record<string, unknown>;
    const status = readString(record, ["status"], "Never run");
    const finishedAt = readString(record, ["finishedAt"], "");
    return {
      label: status || "Never run",
      completedAt: finishedAt ? parseDateOrNow(finishedAt) : null,
    };
  }

  const label = readString(metadata, ["lastRunStatus"], "Never run");
  const timestamp = readString(metadata, ["lastRunAt", "lastRunTimestamp"], "");

  return {
    label: label || "Never run",
    completedAt: timestamp ? parseDateOrNow(timestamp) : null,
  };
}

function readString(metadata: Record<string, unknown>, keys: readonly string[], fallback = "") {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }

  return fallback;
}

function parseDateOrNow(value: string | undefined | null) {
  if (!value) {
    return new Date();
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return new Date();
  }

  return new Date(timestamp);
}

function getFileExtension(filename: string) {
  const lastDotIndex = filename.lastIndexOf(".");
  if (lastDotIndex === -1 || lastDotIndex === filename.length - 1) {
    return "";
  }

  return filename.slice(lastDotIndex).toLowerCase();
}

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
