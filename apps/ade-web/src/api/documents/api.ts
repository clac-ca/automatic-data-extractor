import { client } from "@api/client";
import { apiFetch } from "@api/client";
import { ApiError } from "@api/errors";
import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@api/listing";
import type { components } from "@schema";

export type DocumentRecord = components["schemas"]["DocumentOut"] & { etag?: string | null };
export type DocumentListRow = components["schemas"]["DocumentListRow"] & { etag?: string | null };
export type DocumentListPage = Omit<components["schemas"]["DocumentListPage"], "items"> & {
  items?: DocumentListRow[] | null;
};
export type DocumentPageResult = DocumentListPage;
export type DocumentChangeEntry = components["schemas"]["DocumentChangeEntry"];
export type DocumentChangesPage = components["schemas"]["DocumentChangesPage"];
export type DocumentStatus = components["schemas"]["DocumentStatus"];
export type DocumentSheet = components["schemas"]["DocumentSheet"];
export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];
export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";
export type TagMode = "any" | "all";

export class DocumentChangesResyncError extends Error {
  readonly latestCursor: string;
  readonly oldestCursor: string | null;

  constructor(latestCursor: string, oldestCursor: string | null = null) {
    super("Document changes cursor is too old; resync required.");
    this.name = "DocumentChangesResyncError";
    this.latestCursor = latestCursor;
    this.oldestCursor = oldestCursor;
  }
}

export type ListDocumentsQuery = {
  limit: number;
  cursor?: string | null;
  sort?: string | null;
  filters?: FilterItem[] | string | null;
  joinOperator?: FilterJoinOperator;
  q?: string | null;
  includeTotal?: boolean;
  includeFacets?: boolean;
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
    limit: number;
    cursor?: string | null;
    filters?: FilterItem[] | string | null;
    joinOperator?: FilterJoinOperator;
    q?: string | null;
    includeTotal?: boolean;
    includeFacets?: boolean;
  },
  signal?: AbortSignal,
): Promise<DocumentPageResult> {
  const query = buildListQuery({
    sort: options.sort ?? null,
    limit: options.limit > 0 ? options.limit : DEFAULT_DOCUMENTS_PAGE_SIZE,
    cursor: options.cursor ?? null,
    q: options.q ?? null,
    filters: options.filters,
    joinOperator: options.joinOperator,
    includeTotal: options.includeTotal,
    includeFacets: options.includeFacets,
  });

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents", {
    params: { path: { workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected document page payload.");
  return data;
}

export async function fetchWorkspaceDocumentChanges(
  workspaceId: string,
  options: { cursor: string; limit?: number; includeRows?: boolean },
  signal?: AbortSignal,
): Promise<DocumentChangesPage> {
  const query = new URLSearchParams({
    cursor: options.cursor,
  });
  if (typeof options.limit === "number") {
    query.set("limit", String(options.limit));
  }
  if (options.includeRows) {
    query.set("includeRows", "true");
  }

  const response = await apiFetch(
    `/api/v1/workspaces/${workspaceId}/documents/changes?${query.toString()}`,
    { signal },
  );

  if (response.status === 410) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: { error?: string; latestCursor?: string; oldestCursor?: string } }
      | null;
    const latestCursor = payload?.detail?.latestCursor;
    const oldestCursor = payload?.detail?.oldestCursor ?? null;
    if (latestCursor) {
      throw new DocumentChangesResyncError(latestCursor, oldestCursor);
    }
  }

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  const data = (await response.json().catch(() => null)) as DocumentChangesPage | null;
  if (!data) {
    throw new Error("Expected document changes payload.");
  }
  return data;
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

  const headers: Record<string, string> = {};
  if (options.ifMatch) {
    headers["If-Match"] = options.ifMatch;
  }

  const { data } = await client.PATCH("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
    body,
    headers: Object.keys(headers).length > 0 ? headers : undefined,
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function deleteWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  const headers: Record<string, string> = {};
  if (options.ifMatch) {
    headers["If-Match"] = options.ifMatch;
  }

  await client.DELETE("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
    headers: Object.keys(headers).length > 0 ? headers : undefined,
  });
}

export async function deleteWorkspaceDocumentsBatch(
  workspaceId: string,
  documentIds: string[],
): Promise<string[]> {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/batch/delete", {
    params: { path: { workspaceId } },
    body: { documentIds },
  });

  if (!data) throw new Error("Expected delete response.");
  return data.documentIds ?? [];
}

export async function archiveWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  options: { ifMatch?: string | null } = {},
): Promise<DocumentRecord> {
  const headers: Record<string, string> = {};
  if (options.ifMatch) {
    headers["If-Match"] = options.ifMatch;
  }
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/archive", {
    params: { path: { workspaceId, documentId } },
    headers: Object.keys(headers).length > 0 ? headers : undefined,
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function restoreWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  options: { ifMatch?: string | null } = {},
): Promise<DocumentRecord> {
  const headers: Record<string, string> = {};
  if (options.ifMatch) {
    headers["If-Match"] = options.ifMatch;
  }
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/{documentId}/restore", {
    params: { path: { workspaceId, documentId } },
    headers: Object.keys(headers).length > 0 ? headers : undefined,
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
