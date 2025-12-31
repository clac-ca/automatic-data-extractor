import { ApiError } from "@api";
import { client } from "@api/client";
import type { RunResource } from "@schema";

import type {
  DocumentLastRun,
  DocumentListRow,
  DocumentPageResult,
  DocumentRecord,
  DocumentStatus,
  DocumentsFilters,
  ListDocumentsQuery,
  RunMetricsResource,
  WorkspaceMemberPage,
  WorkbookPreview,
  WorkbookSheet,
} from "./types";
import {
  buildHeaders,
  buildNormalizedFilename,
  extractFilename,
  normalizeCell,
  normalizeRow,
  triggerDownload,
} from "./utils";

export const DOCUMENTS_PAGE_SIZE = 50;
export const MAX_PREVIEW_ROWS = 200;

export const documentsKeys = {
  root: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.root(), workspaceId] as const,
  list: (
    workspaceId: string,
    options: { sort: string | null; pageSize: number; filters?: DocumentsFilters; search?: string },
  ) => [...documentsKeys.workspace(workspaceId), "list", options] as const,
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
  options: {
    sort: string | null;
    page: number;
    pageSize: number;
    query?: Partial<ListDocumentsQuery>;
  },
  signal?: AbortSignal,
): Promise<DocumentPageResult> {
  const query: ListDocumentsQuery = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    page_size: options.pageSize > 0 ? options.pageSize : DOCUMENTS_PAGE_SIZE,
    include_total: false,
    ...(options.query ?? {}),
  };

  const { data, response } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected document page payload.");
  const changesCursorHeader = response?.headers?.get("x-ade-changes-cursor");
  return {
    ...data,
    changesCursorHeader,
  };
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

export async function fetchWorkspaceDocumentRowById(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentListRow> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents/{document_id}/listRow", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    signal,
  });
  if (!data) throw new Error("Expected document list row payload.");
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
        active_sheet_only: false,
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
  return data.documents ?? [];
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

export async function patchWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  payload: { assigneeUserId?: string | null; metadata?: Record<string, unknown> | null },
): Promise<DocumentRecord> {
  const body: {
    assignee_user_id?: string | null;
    metadata?: Record<string, unknown> | null;
  } = {};
  if ("assigneeUserId" in payload) {
    body.assignee_user_id = payload.assigneeUserId ?? null;
  }
  if ("metadata" in payload) {
    body.metadata = payload.metadata ?? null;
  }

  const { data } = await client.PATCH("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
    body,
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function archiveWorkspaceDocument(workspaceId: string, documentId: string): Promise<DocumentRecord> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/{document_id}/archive", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function restoreWorkspaceDocument(workspaceId: string, documentId: string): Promise<DocumentRecord> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/{document_id}/restore", {
    params: { path: { workspace_id: workspaceId, document_id: documentId } },
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function archiveWorkspaceDocumentsBatch(
  workspaceId: string,
  documentIds: string[],
): Promise<DocumentRecord[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/archive", {
    params: { path: { workspace_id: workspaceId } },
    body: { document_ids: documentIds },
  });

  if (!data) throw new Error("Expected updated document records.");
  return data.documents ?? [];
}

export async function restoreWorkspaceDocumentsBatch(
  workspaceId: string,
  documentIds: string[],
): Promise<DocumentRecord[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents/batch/restore", {
    params: { path: { workspace_id: workspaceId } },
    body: { document_ids: documentIds },
  });

  if (!data) throw new Error("Expected updated document records.");
  return data.documents ?? [];
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

export function getDocumentOutputRun(document: DocumentListRow | DocumentRecord | null | undefined): DocumentLastRun | null {
  if (!document) return null;
  if (document.last_successful_run) return document.last_successful_run;
  if (document.last_run?.status === "succeeded") return document.last_run;
  return null;
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
