import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { RunResource } from "@schema";

import type {
  ApiDocumentStatus,
  DocumentEntry,
  DocumentLastRun,
  DocumentPage,
  DocumentRecord,
  DocumentStatus,
  FileType,
  ListDocumentsQuery,
  MappingHealth,
  RunMetricsResource,
  WorkspaceMemberPage,
  WorkbookPreview,
  WorkbookSheet,
} from "./types";
import {
  buildHeaders,
  buildNormalizedFilename,
  extractFilename,
  fileTypeFromName,
  formatBytes,
  normalizeCell,
  normalizeRow,
  parseTimestamp,
  triggerDownload,
} from "./utils";

export const DOCUMENTS_PAGE_SIZE = 50;
export const MAX_PREVIEW_ROWS = 200;

export const documentsKeys = {
  root: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.root(), workspaceId] as const,
  list: (workspaceId: string, sort: string | null) => [...documentsKeys.workspace(workspaceId), "list", { sort }] as const,
  members: (workspaceId: string) => [...documentsKeys.workspace(workspaceId), "members"] as const,
  document: (workspaceId: string, documentId: string) =>
    [...documentsKeys.workspace(workspaceId), "document", documentId] as const,
  runsForDocument: (workspaceId: string, documentId: string) =>
    [...documentsKeys.workspace(workspaceId), "runs", { input_document_id: documentId }] as const,
  run: (runId: string) => [...documentsKeys.root(), "run", runId] as const,
  runMetrics: (runId: string) => [...documentsKeys.run(runId), "metrics"] as const,
  workbook: (url: string) => [...documentsKeys.root(), "workbook", url] as const,
};

export async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: { sort: string | null; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<DocumentPage> {
  const query: ListDocumentsQuery = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected document page payload.");
  return data;
}

export async function fetchWorkspaceDocumentById(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    signal,
  });
  if (!data) throw new Error("Expected document payload.");
  return data;
}

export async function fetchWorkspaceMembers(workspaceId: string, signal?: AbortSignal): Promise<WorkspaceMemberPage> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    signal,
  });
  if (!data) throw new Error("Expected workspace member page payload.");
  return data;
}

export async function fetchWorkspaceRunsForDocument(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<RunResource[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/runs", {
    params: {
      path: { workspace_id: workspaceId },
      query: { page: 1, page_size: 25, include_total: false, input_document_id: documentId },
    },
    signal,
  });

  if (!data) throw new Error("Expected run page payload.");
  return data.items ?? [];
}

export async function fetchRunMetrics(runId: string, signal?: AbortSignal): Promise<RunMetricsResource | null> {
  try {
    const { data } = await client.GET("/api/v1/runs/{run_id}/metrics", {
      params: { path: { run_id: runId } },
      signal,
    });
    return data ?? null;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchWorkbookPreview(url: string, signal?: AbortSignal): Promise<WorkbookPreview> {
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) throw new Error("Unable to fetch processed workbook.");

  const buffer = await response.arrayBuffer();
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(buffer, { type: "array" });

  const sheets = workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false, blankrows: false }) as unknown[][];
    const totalRows = rows.length;
    const totalColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const truncatedRows = totalRows > MAX_PREVIEW_ROWS;

    const visibleRows = rows.slice(0, MAX_PREVIEW_ROWS).map((row) => row.map((cell) => normalizeCell(cell)));

    const columnCount = Math.max(visibleRows[0]?.length ?? 0, totalColumns, 1);
    const headers = buildHeaders(visibleRows[0] ?? [], columnCount);
    const bodyRows = visibleRows.slice(1).map((row) => normalizeRow(row as string[], headers.length));

    return {
      name,
      headers,
      rows: bodyRows as string[][],
      totalRows,
      totalColumns,
      truncatedRows,
      truncatedColumns: false,
    } satisfies WorkbookSheet;
  });

  return { sheets };
}

export function buildDocumentEntry(document: DocumentRecord): DocumentEntry {
  const status = deriveDocumentStatus(document);
  const uploader = deriveUploaderLabel(document);
  const createdAt = parseTimestamp(document.created_at);
  const updatedAt = resolveDocumentUpdatedAt(document);
  const stage = buildStageLabel(status, document.last_run);
  const mapping = deriveMappingHealth(document);

  const fileType: FileType = fileTypeFromName(document.name);

  return {
    id: document.id,
    name: document.name,
    status,
    fileType,
    uploader,
    tags: document.tags ?? [],
    createdAt,
    updatedAt,
    size: formatBytes(document.byte_size),
    stage,
    error: status === "failed" ? buildDocumentError(document) : undefined,
    mapping,

    // Collaborative defaults (overridden by model)
    assigneeKey: null,
    assigneeLabel: null,
    commentCount: 0,

    record: document,
  };
}

export async function downloadOriginalDocument(
  workspaceId: string,
  documentId: string,
  fallbackName: string,
): Promise<string> {
  const response = await fetch(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/download`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error("Unable to download original file.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? fallbackName;
  triggerDownload(blob, filename);
  return filename;
}

export async function downloadRunOutput(outputDownloadUrl: string, fallbackName: string): Promise<string> {
  const response = await fetch(outputDownloadUrl, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to download processed output.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? buildNormalizedFilename(fallbackName);
  triggerDownload(blob, filename);
  return filename;
}

export async function downloadRunOutputById(runId: string, fallbackName: string): Promise<string> {
  const response = await fetch(`/api/v1/runs/${runId}/output/download`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to download processed output.");
  const blob = await response.blob();
  const filename = extractFilename(response.headers.get("content-disposition")) ?? buildNormalizedFilename(fallbackName);
  triggerDownload(blob, filename);
  return filename;
}

export async function createRunForDocument(configurationId: string, documentId: string): Promise<RunResource> {
  const { data } = await client.POST("/api/v1/configurations/{configuration_id}/runs", {
    params: { path: { configuration_id: configurationId } },
    body: {
      options: {
        dry_run: false,
        validate_only: false,
        force_rebuild: false,
        debug: false,
        input_document_id: documentId,
      },
    },
  });

  if (!data) throw new Error("Unable to create run.");
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

export async function deleteWorkspaceDocument(workspaceId: string, documentId: string): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
  });
}

export async function deleteWorkspaceDocumentsBatch(workspaceId: string, documentIds: string[]): Promise<string[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/delete", {
    params: { path: { workspace_id: workspaceId } },
    body: { document_ids: documentIds },
  });

  if (!data) throw new Error("Expected delete response.");
  return data.document_ids ?? [];
}

export function runOutputDownloadUrl(run: RunResource): string | null {
  if (run.output?.download_url) return run.output.download_url;
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
      return "queued";
    default:
      return "queued";
  }
}

function deriveDocumentStatus(document: DocumentRecord): DocumentStatus {
  if (document.status === "archived") return "archived";

  const lastRunStatus = document.last_run?.status;
  switch (lastRunStatus) {
    case "queued":
      return "queued";
    case "running":
      return "processing";
    case "succeeded":
      return "ready";
    case "failed":
    case "cancelled":
      return "failed";
    default:
      break;
  }

  return mapApiStatus(document.status);
}

function resolveDocumentUpdatedAt(document: DocumentRecord): number {
  const updatedAt = parseTimestamp(document.updated_at);
  if (!document.last_run_at) return updatedAt;

  const lastRunAt = parseTimestamp(document.last_run_at);
  return Math.max(updatedAt, lastRunAt);
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
  return ownerName || ownerEmail ? ownerName ?? ownerEmail ?? null : null;
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
  if (attention !== null || unmapped !== null) {
    return { attention: attention ?? 0, unmapped: unmapped ?? 0 };
  }

  return null;
}

function buildStageLabel(status: DocumentStatus, lastRun: DocumentLastRun | null | undefined) {
  if (status === "queued") return "Queued for processing";
  if (status === "processing") {
    if (lastRun?.status === "queued") return "Queued for processing";
    return "Processing output";
  }
  return undefined;
}

function buildDocumentError(document: DocumentRecord) {
  const message = document.last_run?.message?.trim();
  return {
    summary: message ?? "Processing failed",
    detail: message ?? "We could not complete normalization for this file.",
    nextStep: "Retry now or fix mapping later.",
  };
}

export function buildStatusDescription(status: DocumentStatus, run?: RunResource | null) {
  switch (status) {
    case "ready":
      return "Processed output ready to download.";
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
