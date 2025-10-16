import { ApiError } from "../../../shared/api/client";
import type { DocumentRecord, DocumentStatus } from "../../../shared/types/documents";
import { trackEvent } from "../../../shared/telemetry/events";

export type UploaderFilterValue = "all" | "me";

export type SortColumn = "name" | "status" | "source" | "uploadedAt" | "lastRunAt" | "byteSize";
export type SortDirection = "asc" | "desc";

export interface SortState {
  readonly column: SortColumn;
  readonly direction: SortDirection;
}

const COLUMN_TO_PARAM: Record<SortColumn, string> = {
  name: "name",
  status: "status",
  source: "source",
  uploadedAt: "created_at",
  lastRunAt: "last_run_at",
  byteSize: "byte_size",
};

const PARAM_TO_COLUMN = Object.fromEntries(
  Object.entries(COLUMN_TO_PARAM).map(([column, param]) => [param, column as SortColumn]),
) as Record<string, SortColumn>;

export const DEFAULT_SORT_STATE: SortState = { column: "uploadedAt", direction: "desc" };
export const DEFAULT_SORT_PARAM = "-created_at";

export function parseSortParam(param: string | undefined | null): SortState {
  if (!param) {
    return DEFAULT_SORT_STATE;
  }
  const descending = param.startsWith("-");
  const field = descending ? param.slice(1) : param;
  const column = PARAM_TO_COLUMN[field] ?? DEFAULT_SORT_STATE.column;
  const direction: SortDirection = descending ? "desc" : "asc";
  return { column, direction };
}

export function toSortParam(state: SortState): string {
  const field = COLUMN_TO_PARAM[state.column];
  const prefix = state.direction === "desc" ? "-" : "";
  return `${prefix}${field}`;
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
  readonly uploaderId: string | null;
  readonly uploaderName: string;
  readonly uploaderEmail: string | null;
  readonly lastRunAt: Date | null;
  readonly metadata: Record<string, unknown>;
  readonly expiresAt: Date;
  readonly updatedAt: Date;
  readonly deletedAt: Date | null;
}

export function toDocumentRows(records: readonly DocumentRecord[] | undefined): DocumentRow[] {
  if (!records) {
    return [];
  }

  return records.map((record) => {
    const uploaderName = record.uploader?.name?.trim() || record.uploader?.email || "Unknown";
    return {
      id: record.document_id,
      name: record.name,
      status: record.status,
      source: record.source,
      tags: [...(record.tags ?? [])],
      uploadedAt: parseRequiredDate(record.created_at),
      byteSize: record.byte_size,
      contentType: record.content_type,
      uploaderId: record.uploader?.id ?? null,
      uploaderName,
      uploaderEmail: record.uploader?.email ?? null,
      lastRunAt: parseOptionalDate(record.last_run_at),
      metadata: record.metadata ?? {},
      expiresAt: parseRequiredDate(record.expires_at),
      updatedAt: parseRequiredDate(record.updated_at),
      deletedAt: parseOptionalDate(record.deleted_at),
    } satisfies DocumentRow;
  });
}

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

export interface SplitFilesResult {
  readonly accepted: File[];
  readonly rejected: File[];
}

export function splitSupportedFiles(files: readonly File[]): SplitFilesResult {
  const accepted: File[] = [];
  const rejected: File[] = [];
  const allowed = new Set(SUPPORTED_FILE_EXTENSIONS.map((value) => value.toLowerCase()));

  for (const file of files) {
    const extension = getFileExtension(file.name);
    if (extension && allowed.has(extension)) {
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
  switch (status) {
    case "uploaded":
      return "Uploaded";
    case "processing":
      return "Processing";
    case "processed":
      return "Processed";
    case "failed":
      return "Failed";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

export function formatLastRunLabel(value: Date | null) {
  if (!value) {
    return "Never";
  }
  return formatRelativeTime(value);
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

export function trackDocumentsEvent(
  action: string,
  workspaceId: string,
  payload: Record<string, unknown> = {},
) {
  trackEvent({
    name: `documents.${action}`,
    payload: { workspaceId, ...payload },
  });
}

function parseRequiredDate(value: string) {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? new Date() : new Date(timestamp);
}

function parseOptionalDate(value: string | null) {
  if (!value) {
    return null;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : new Date(timestamp);
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
