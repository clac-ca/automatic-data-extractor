import { client } from "@api/client";
import type { FilterItem, FilterJoinOperator } from "@api/listing";
import { encodeFilters } from "@api/listing";
import type { components } from "@schema";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentListPage = components["schemas"]["DocumentListPage"];
export type DocumentPageResult = DocumentListPage & { changesCursorHeader?: string | null };
export type DocumentStatus = components["schemas"]["DocumentStatus"];
export type DocumentSheet = components["schemas"]["DocumentSheet"];
export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];
export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";
export type TagMode = "any" | "all";

export type ListDocumentsQuery = {
  page: number;
  perPage: number;
  sort?: string | null;
  filters?: FilterItem[];
  joinOperator?: FilterJoinOperator;
  q?: string | null;
};

const DEFAULT_DOCUMENTS_PAGE_SIZE = 50;

export async function fetchDocumentSheets(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentSheet[]> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets",
    {
      params: { path: { workspaceId, documentId } },
      signal,
    },
  );

  return (data ?? []) as DocumentSheet[];
}

export async function fetchDocumentPreview(
  workspaceId: string,
  documentId: string,
  options: {
    maxRows?: number;
    maxColumns?: number;
    trimEmptyRows?: boolean;
    trimEmptyColumns?: boolean;
    sheetName?: string | null;
    sheetIndex?: number | null;
  } = {},
  signal?: AbortSignal,
): Promise<WorkbookSheetPreview> {
  const query: Record<string, unknown> = {};
  if (options.maxRows !== undefined) query.maxRows = options.maxRows;
  if (options.maxColumns !== undefined) query.maxColumns = options.maxColumns;
  if (options.trimEmptyRows !== undefined) query.trimEmptyRows = options.trimEmptyRows;
  if (options.trimEmptyColumns !== undefined) query.trimEmptyColumns = options.trimEmptyColumns;
  if (options.sheetName) query.sheetName = options.sheetName;
  if (typeof options.sheetIndex === "number") query.sheetIndex = options.sheetIndex;

  const { data } = await client.GET(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/preview",
    {
      params: { path: { workspaceId, documentId }, query },
      signal,
    },
  );

  if (!data) throw new Error("Expected document preview payload.");
  return data;
}

export async function fetchWorkspaceDocuments(
  workspaceId: string,
  options: {
    sort: string | null;
    page: number;
    perPage: number;
    filters?: FilterItem[];
    joinOperator?: FilterJoinOperator;
    q?: string | null;
  },
  signal?: AbortSignal,
): Promise<DocumentPageResult> {
  const query = {
    sort: options.sort ?? undefined,
    page: options.page > 0 ? options.page : 1,
    perPage: options.perPage > 0 ? options.perPage : DEFAULT_DOCUMENTS_PAGE_SIZE,
    q: options.q ?? undefined,
    filters: encodeFilters(options.filters),
    joinOperator: options.joinOperator,
  };

  const { data, response } = await client.GET("/api/v1/workspaces/{workspaceId}/documents", {
    params: { path: { workspaceId }, query },
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
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
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
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}/listrow", {
    params: { path: { workspaceId, documentId } },
    signal,
  });
  if (!data) throw new Error("Expected document list row payload.");
  return data;
}

export async function patchWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  payload: { assigneeId?: string | null; metadata?: Record<string, unknown> | null },
  options: { ifMatch?: string | null } = {},
): Promise<DocumentRecord> {
  const body: {
    assigneeId?: string | null;
    metadata?: Record<string, unknown> | null;
  } = {};
  if ("assigneeId" in payload) {
    body.assigneeId = payload.assigneeId ?? null;
  }
  if ("metadata" in payload) {
    body.metadata = payload.metadata ?? null;
  }

  const { data } = await client.PATCH("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
    body,
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function deleteWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });
}

export async function deleteWorkspaceDocumentsBatch(workspaceId: string, documentIds: string[]): Promise<string[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/batch/delete", {
    params: { path: { workspaceId } },
    body: { documentIds },
  });

  if (!data) throw new Error("Expected delete response.");
  return data.documentIds ?? [];
}

export async function archiveWorkspaceDocument(workspaceId: string, documentId: string): Promise<DocumentRecord> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/archive", {
    params: { path: { workspaceId, documentId } },
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function restoreWorkspaceDocument(workspaceId: string, documentId: string): Promise<DocumentRecord> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/restore", {
    params: { path: { workspaceId, documentId } },
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function archiveWorkspaceDocumentsBatch(
  workspaceId: string,
  documentIds: string[],
): Promise<DocumentRecord[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/batch/archive", {
    params: { path: { workspaceId } },
    body: { documentIds },
  });

  if (!data) throw new Error("Expected updated document records.");
  return data.documents ?? [];
}

export async function restoreWorkspaceDocumentsBatch(
  workspaceId: string,
  documentIds: string[],
): Promise<DocumentRecord[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/batch/restore", {
    params: { path: { workspaceId } },
    body: { documentIds },
  });

  if (!data) throw new Error("Expected updated document records.");
  return data.documents ?? [];
}
