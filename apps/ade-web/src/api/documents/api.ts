import { client } from "@api/client";
import type { components, paths } from "@schema";

export type DocumentRecord = components["schemas"]["DocumentOut"];
export type DocumentListRow = components["schemas"]["DocumentListRow"];
export type DocumentListPage = components["schemas"]["DocumentListPage"];
export type DocumentPageResult = DocumentListPage & { changesCursorHeader?: string | null };
export type DocumentStatus = components["schemas"]["DocumentDisplayStatus"];
export type DocumentSheet = components["schemas"]["DocumentSheet"];
export type FileType = "xlsx" | "xls" | "csv" | "pdf" | "unknown";
export type TagMode = "any" | "all";

type BaseListDocumentsQuery = NonNullable<
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"]
>;

export type ListDocumentsQuery = BaseListDocumentsQuery & {
  q?: string;
  display_status?: DocumentStatus[];
  file_type?: FileType[];
  tags?: string[];
  tag_mode?: TagMode;
  assignee_user_id?: string[];
  assignee_unassigned?: boolean;
};

const DEFAULT_DOCUMENTS_PAGE_SIZE = 50;

export async function fetchDocumentSheets(
  workspaceId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentSheet[]> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
      signal,
    },
  );

  return (data ?? []) as DocumentSheet[];
}

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
    page_size: options.pageSize > 0 ? options.pageSize : DEFAULT_DOCUMENTS_PAGE_SIZE,
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
