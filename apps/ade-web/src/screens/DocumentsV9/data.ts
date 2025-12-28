import { client } from "@shared/api/client";
import type { UploadQueueItem } from "@shared/uploads/queue";
import type { DocumentUploadResponse } from "@shared/documents";

import type {
  ApiDocumentStatus,
  DocumentEntry,
  DocumentLastRun,
  DocumentPage,
  DocumentRecord,
  DocumentStatus,
  DocumentsFilters,
  MappingHealth,
  RunPage,
  RunResource,
  WorkbookPreview,
  WorkbookSheet,
} from "./types";
import {
  buildHeaders,
  buildNormalizedFilename,
  extractFilename,
  formatBytes,
  inferFileType,
  normalizeCell,
  normalizeRow,
  parseTimestamp,
  triggerDownload,
} from "./utils";

export const DOCUMENTS_PAGE_SIZE = 50;
export const MAX_PREVIEW_ROWS = 200;
export const MAX_PREVIEW_COLUMNS = 24;

export const documentsV9Keys = {
  root: () => ["documents-v9"] as const,
  workspace: (workspaceId: string) => [...documentsV9Keys.root(), workspaceId] as const,
  list: (
    workspaceId: string,
    options: { sort: string | null; search: string; filters: DocumentsFilters },
  ) => [...documentsV9Keys.workspace(workspaceId), "list", options] as const,
  workbook: (url: string) => [...documentsV9Keys.root(), "workbook", url] as const,
  runsForDocument: (workspaceId: string, documentId: string) =>
    [...documentsV9Keys.workspace(workspaceId), "runs", { documentId }] as const,
};

export async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: {
    sort: string | null;
    page: number;
    pageSize: number;
    search: string;
    filters: DocumentsFilters;
  },
  signal?: AbortSignal,
): Promise<DocumentPage> {
  const trimmedSearch = options.search.trim();
  const statusFilters = mapUiStatusesToApi(options.filters.statuses);
  const fileTypeFilters = options.filters.fileTypes.filter((type) => type !== "unknown");
  const query = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
    ...(trimmedSearch.length >= 2 ? { q: trimmedSearch } : {}),
    ...(statusFilters.length > 0 ? { status: statusFilters } : {}),
    ...(fileTypeFilters.length > 0 ? { file_type: fileTypeFilters } : {}),
    ...(options.filters.tags.length > 0
      ? { tags: options.filters.tags, tag_mode: options.filters.tagMode }
      : {}),
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected document page payload.");
  return data;
}

export async function fetchWorkspaceRunsForDocument(
  workspaceId: string,
  documentId: string,
  options: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<RunPage> {
  const query = {
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : 50,
    include_total: false,
    input_document_id: documentId,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/runs", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected run page payload.");
  return data;
}

export async function createRunForDocument(
  workspaceId: string,
  documentId: string,
): Promise<RunResource> {
  const body = {
    input_document_id: documentId,
  };

  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/runs", {
    params: { path: { workspace_id: workspaceId } },
    body,
  });

  if (!data) throw new Error("Expected run resource.");
  return data;
}

export async function patchWorkspaceDocumentTags(
  workspaceId: string,
  documentId: string,
  patch: { add?: string[]; remove?: string[] },
): Promise<DocumentRecord> {
  const { data } = await client.PATCH("/api/v1/workspaces/{workspace_id}/documents/{document_id}/tags", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    body: patch,
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function patchWorkspaceDocumentTagsBatch(
  workspaceId: string,
  documentIds: string[],
  patch: { add?: string[]; remove?: string[] },
): Promise<DocumentRecord[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/tags", {
    params: { path: { workspace_id: workspaceId } },
    body: { document_ids: documentIds, ...patch },
  });

  if (!data) throw new Error("Expected updated document records.");
  return data.documents;
}

export function runOutputDownloadUrl(run: RunResource): string | null {
  // Prefer server-provided direct/signed URL if present.
  if (run.output?.download_url) return run.output.download_url;
  // Otherwise use the authenticated API link.
  if (run.links?.output_download) return run.links.output_download;
  return null;
}

export function runHasDownloadableOutput(run: RunResource | null) {
  if (!run) return false;
  if (run.status !== "succeeded") return false;
  return Boolean(runOutputDownloadUrl(run));
}

export function getDocumentOutputRun(document: DocumentRecord | null | undefined): DocumentLastRun | null {
  if (!document) return null;
  if (document.last_successful_run) return document.last_successful_run;
  if (document.last_run?.status === "succeeded") return document.last_run;
  return null;
}

export async function downloadRunOutput(runId: string, fallbackName: string): Promise<string> {
  const url = `/api/v1/runs/${runId}/output/download`;
  return downloadFileFromUrl(url, buildNormalizedFilename(fallbackName));
}

export async function downloadWorkspaceDocumentOriginal(
  workspaceId: string,
  documentId: string,
  fallbackName: string,
): Promise<string> {
  const url = `/api/v1/workspaces/${workspaceId}/documents/${documentId}/download`;
  return downloadFileFromUrl(url, fallbackName);
}

async function downloadFileFromUrl(url: string, fallbackName: string): Promise<string> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to download file.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? fallbackName;
  triggerDownload(blob, filename);
  return filename;
}

export async function fetchWorkbookPreview(url: string, signal?: AbortSignal): Promise<WorkbookPreview> {
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) throw new Error("Unable to fetch workbook for preview.");
  const buffer = await response.arrayBuffer();

  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });

  const sheets = workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, blankrows: false }) as unknown[][];
    const totalRows = rows.length;
    const totalColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const truncatedRows = totalRows > MAX_PREVIEW_ROWS;
    const truncatedColumns = totalColumns > MAX_PREVIEW_COLUMNS;

    const visibleRows = rows
      .slice(0, MAX_PREVIEW_ROWS)
      .map((row) => row.slice(0, MAX_PREVIEW_COLUMNS).map((cell) => normalizeCell(cell)));

    const columnCount = Math.max(visibleRows[0]?.length ?? 0, totalColumns, 1);
    const headers = buildHeaders(visibleRows[0] ?? [], columnCount);
    const bodyRows = visibleRows.slice(1).map((row) => normalizeRow(row, headers.length));

    return {
      name,
      headers,
      rows: bodyRows,
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns,
    } satisfies WorkbookSheet;
  });

  return { sheets };
}

export function buildDocumentEntry(
  document: DocumentRecord,
  options: { upload?: UploadQueueItem<DocumentUploadResponse> } = {},
): DocumentEntry {
  const status = mapApiStatus(document.status);
  const uploader = deriveUploaderLabel(document);
  const createdAt = parseTimestamp(document.created_at);
  const updatedAt = parseTimestamp(document.updated_at);
  const stage = buildStageLabel(status, document.last_run);
  const mapping = deriveMappingHealth(document);
  const fileType = inferFileType(document.name, document.content_type ?? null);

  return {
    id: document.id,
    name: document.name,
    status,
    uploader,
    tags: document.tags ?? [],
    createdAt,
    updatedAt,
    size: formatBytes(document.byte_size),
    fileType,
    stage,
    error: status === "failed" ? buildDocumentError(document) : undefined,
    mapping,
    record: document,
    upload: options.upload,
  };
}

export function buildUploadEntry(
  item: UploadQueueItem<DocumentUploadResponse>,
  uploaderLabel: string,
  createdAt: number,
): DocumentEntry {
  const isFailed = item.status === "failed";
  const isUploading = item.status === "uploading";

  const status: DocumentStatus = isFailed ? "failed" : isUploading ? "processing" : "queued";
  const progress = isUploading ? item.progress.percent : undefined;
  const stage = isFailed ? "Upload failed" : isUploading ? "Uploading" : "Queued for upload";
  const error = isFailed
    ? {
        summary: item.error ?? "Upload failed",
        detail: "We could not upload this file. Check the connection and retry.",
        nextStep: "Retry now or remove the upload.",
      }
    : undefined;

  const fileType = inferFileType(item.file.name);

  return {
    id: item.id,
    name: item.file.name,
    status,
    uploader: uploaderLabel,
    tags: [],
    createdAt,
    updatedAt: createdAt,
    size: formatBytes(item.file.size),
    fileType,
    progress,
    stage,
    error,
    mapping: { attention: 0, unmapped: 0, pending: true },
    record: item.response,
    upload: item,
  };
}

export function mapApiStatus(status: ApiDocumentStatus): DocumentStatus {
  switch (status) {
    case "processed":
      return "ready";
    case "processing":
      return "processing";
    case "failed":
      return "failed";
    case "archived":
      return "archived";
    case "uploaded":
    default:
      return "queued";
  }
}

function mapUiStatusesToApi(statuses: DocumentStatus[]): ApiDocumentStatus[] {
  return statuses.map((status) => {
    switch (status) {
      case "ready":
        return "processed";
      case "processing":
        return "processing";
      case "failed":
        return "failed";
      case "archived":
        return "archived";
      case "queued":
      default:
        return "uploaded";
    }
  });
}

export function deriveUploaderLabel(document: DocumentRecord): string | null {
  const metadata = document.metadata ?? {};
  const ownerFromMetadata = readOwnerFromMetadata(metadata);
  if (ownerFromMetadata) return ownerFromMetadata;

  const uploader = document.uploader;
  if (uploader?.name || uploader?.email) return uploader.name ?? uploader.email ?? "Unassigned";
  return null;
}

function readOwnerFromMetadata(metadata: Record<string, unknown>): string | null {
  const ownerName = typeof metadata.owner === "string" ? metadata.owner : undefined;
  const ownerEmail = typeof metadata.owner_email === "string" ? metadata.owner_email : undefined;
  return ownerName ?? ownerEmail ?? null;
}

export function deriveMappingHealth(document: DocumentRecord): MappingHealth {
  const metadata = document.metadata ?? {};
  const fromMetadata = readMappingFromMetadata(metadata);
  if (fromMetadata) return fromMetadata;

  if (document.status === "uploaded" || document.status === "processing") {
    return { attention: 0, unmapped: 0, pending: true };
  }
  return { attention: 0, unmapped: 0 };
}

function readMappingFromMetadata(metadata: Record<string, unknown>): MappingHealth | null {
  const candidate = metadata.mapping ?? metadata.mapping_health ?? metadata.mapping_quality;
  if (candidate && typeof candidate === "object") {
    const record = candidate as Record<string, unknown>;
    const attention =
      typeof record.issues === "number"
        ? record.issues
        : typeof record.attention === "number"
          ? record.attention
          : 0;
    const unmapped = typeof record.unmapped === "number" ? record.unmapped : 0;
    const pending = typeof record.status === "string" && record.status === "pending";
    return { attention, unmapped, pending: pending || undefined };
  }

  const attention = typeof metadata.mapping_issues === "number" ? metadata.mapping_issues : null;
  const unmapped = typeof metadata.unmapped_columns === "number" ? metadata.unmapped_columns : null;
  if (attention !== null || unmapped !== null) return { attention: attention ?? 0, unmapped: unmapped ?? 0 };
  return null;
}

function buildStageLabel(status: DocumentStatus, lastRun: DocumentLastRun | null | undefined) {
  if (status === "queued") return "Queued for processing";
  if (status === "processing") {
    if (lastRun?.status === "queued") return "Queued for processing";
    return "Processing in progress";
  }
  return undefined;
}

function buildDocumentError(document: DocumentRecord) {
  const message = document.last_run?.message?.trim();
  return {
    summary: message ?? "Processing failed",
    detail: message ?? "We could not complete normalization for this file.",
    nextStep: "Reprocess now or inspect run details.",
  };
}

export function buildStatusDescription(status: DocumentStatus, run?: RunResource | null) {
  switch (status) {
    case "ready":
      return "Processed output is available.";
    case "processing":
      if (run?.status === "queued") return "Queued for processing.";
      if (run?.status === "running") return "Processing in progress.";
      return "Processing in progress.";
    case "failed":
      return "Needs attention.";
    case "queued":
      return "Queued and waiting to start.";
    case "archived":
      return "Archived output (read-only).";
    default:
      return "";
  }
}
