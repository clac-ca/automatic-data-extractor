import { client } from "@/api/client";
import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@/api/listing";
import type { components } from "@/types";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentListPage = components["schemas"]["DocumentListPage"];
export type DocumentPageResult = DocumentListPage;
export type DocumentSheet = components["schemas"]["DocumentSheet"];
export type WorkbookSheetPreview = components["schemas"]["WorkbookSheetPreview"];
export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";
export type TagMode = "any" | "all";

export type ListDocumentsQuery = {
  limit: number;
  cursor?: string | null;
  sort?: string | null;
  filters?: FilterItem[] | string | null;
  joinOperator?: FilterJoinOperator;
  q?: string | null;
  includeTotal?: boolean;
  includeFacets?: boolean;
  includeRunMetrics?: boolean;
  includeRunTableColumns?: boolean;
  includeRunFields?: boolean;
};

type DocumentIncludeOptions = {
  includeRunMetrics?: boolean;
  includeRunTableColumns?: boolean;
  includeRunFields?: boolean;
};

function buildDocumentIncludeQuery(options?: DocumentIncludeOptions) {
  if (!options) return {};
  const query: Record<string, unknown> = {};
  if (options.includeRunMetrics) query.includeRunMetrics = true;
  if (options.includeRunTableColumns) query.includeRunTableColumns = true;
  if (options.includeRunFields) query.includeRunFields = true;
  return query;
}

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
    includeRunMetrics?: boolean;
    includeRunTableColumns?: boolean;
    includeRunFields?: boolean;
  },
  signal?: AbortSignal,
): Promise<DocumentPageResult> {
  const query = {
    ...buildListQuery({
      sort: options.sort ?? null,
      limit: options.limit > 0 ? options.limit : DEFAULT_DOCUMENTS_PAGE_SIZE,
      cursor: options.cursor ?? null,
      q: options.q ?? null,
      filters: options.filters,
      joinOperator: options.joinOperator,
      includeTotal: options.includeTotal,
      includeFacets: options.includeFacets,
    }),
    ...buildDocumentIncludeQuery(options),
  };

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents", {
    params: { path: { workspaceId }, query },
    signal,
  });

  if (!data) throw new Error("Expected document page payload.");
  return data;
}


export async function fetchWorkspaceDocumentById(
  workspaceId: string,
  documentId: string,
  options: DocumentIncludeOptions = {},
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const query = buildDocumentIncludeQuery(options);
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId }, query },
    signal,
  });
  if (!data) throw new Error("Expected document payload.");
  return data;
}

export async function fetchWorkspaceDocumentRowById(
  workspaceId: string,
  documentId: string,
  options: DocumentIncludeOptions = {},
  signal?: AbortSignal,
): Promise<DocumentListRow> {
  const query = buildDocumentIncludeQuery(options);
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/{documentId}/listrow", {
    params: { path: { workspaceId, documentId }, query },
    signal,
  });
  if (!data) throw new Error("Expected document list row payload.");
  return data;
}

export async function patchWorkspaceDocument(
  workspaceId: string,
  documentId: string,
  payload: { assigneeId?: string | null; metadata?: Record<string, unknown> | null },
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
  });

  if (!data) throw new Error("Expected updated document record.");
  return data;
}

export async function deleteWorkspaceDocument(
  workspaceId: string,
  documentId: string,
): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
    params: { path: { workspaceId, documentId } },
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

const DEFAULT_ID_FILTER_BATCH = 50;

export async function fetchWorkspaceDocumentRowsByIdFilter(
  workspaceId: string,
  documentIds: string[],
  options: {
    sort: string | null;
    filters?: FilterItem[] | null;
    joinOperator?: FilterJoinOperator;
    q?: string | null;
    includeRunMetrics?: boolean;
    includeRunTableColumns?: boolean;
    includeRunFields?: boolean;
  },
  signal?: AbortSignal,
): Promise<DocumentListRow[]> {
  const uniqueIds = Array.from(new Set(documentIds)).filter((id) => id);
  if (uniqueIds.length === 0) return [];

  const filtersBase = options.filters ?? [];
  const batches: string[][] = [];
  for (let i = 0; i < uniqueIds.length; i += DEFAULT_ID_FILTER_BATCH) {
    batches.push(uniqueIds.slice(i, i + DEFAULT_ID_FILTER_BATCH));
  }

  const byId = new Map<string, DocumentListRow>();
  for (const batch of batches) {
    // Use the list endpoint with `id in [...]` so membership respects the same server-side filters.
    const filters: FilterItem[] = [
      ...filtersBase,
      { id: "id", operator: "in", value: batch },
    ];
    const page = await fetchWorkspaceDocuments(
      workspaceId,
      {
        limit: batch.length,
        sort: options.sort,
        filters,
        joinOperator: options.joinOperator,
        q: options.q,
        includeRunMetrics: options.includeRunMetrics,
        includeRunTableColumns: options.includeRunTableColumns,
        includeRunFields: options.includeRunFields,
      },
      signal,
    );
    (page.items ?? []).forEach((row) => {
      byId.set(row.id, row);
    });
  }

  return Array.from(byId.values());
}
