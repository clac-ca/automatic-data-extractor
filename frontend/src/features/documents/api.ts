import type { QueryFunctionContext } from "@tanstack/react-query";

import { client } from "@shared/api/client";
import type { components, paths } from "@api-types";

export interface ListWorkspaceDocumentsOptions {
  readonly status?: StatusFilterInput;
  readonly search?: string | null;
  readonly sort?: string | null;
}

export async function listWorkspaceDocuments(
  workspaceId: string,
  options: ListWorkspaceDocumentsOptions = {},
  signal?: AbortSignal,
) {
  const query: ListDocumentsQuery = {};
  const statuses = normaliseStatusFilter(options.status);
  if (statuses) {
    query.status = Array.from(statuses);
  }
  const search = options.search?.trim();
  if (search) {
    query.q = search;
  }
  const sort = options.sort?.trim();
  if (sort) {
    query.sort = sort;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace documents response.");
  }

  return data;
}

export async function uploadWorkspaceDocument(workspaceId: string, file: File) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/documents", {
    params: {
      path: { workspace_id: workspaceId },
    },
    body: {
      file: "",
    },
    bodySerializer: () => {
      const formData = new FormData();
      formData.append("file", file);
      return formData;
    },
  });

  if (!data) {
    throw new Error("Expected uploaded document response.");
  }

  return data;
}

export async function deleteWorkspaceDocuments(workspaceId: string, documentIds: readonly string[]) {
  await Promise.all(
    documentIds.map((documentId) =>
      client.DELETE("/api/v1/workspaces/{workspace_id}/documents/{document_id}", {
        params: {
          path: {
            workspace_id: workspaceId,
            document_id: documentId,
          },
        },
      }),
    ),
  );
}

export async function downloadWorkspaceDocument(workspaceId: string, documentId: string) {
  const { data, response } = await client.GET(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          document_id: documentId,
        },
      },
      parseAs: "blob",
    },
  );

  if (!data) {
    throw new Error("Expected document download payload.");
  }

  const filename =
    extractFilename(response.headers.get("content-disposition")) ?? `document-${documentId}`;

  return { blob: data, filename };
}

function extractFilename(header: string | null) {
  if (!header) {
    return null;
  }
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^";]+)"?/i);
  if (filenameMatch?.[1]) {
    return filenameMatch[1];
  }
  return null;
}

export const documentsKeys = {
  all: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.all(), workspaceId] as const,
  list: (
    workspaceId: string,
    status: readonly DocumentStatus[] | null,
    search: string | null,
    sort: string | null,
  ) => [
    ...documentsKeys.workspace(workspaceId),
    "list",
    { status, search, sort },
  ] as const,
};

export type DocumentsStatusFilter = "all" | DocumentStatus | readonly DocumentStatus[];

export interface WorkspaceDocumentsQueryOptions {
  readonly status?: DocumentsStatusFilter;
  readonly search?: string | null;
  readonly sort?: string | null;
}

export function workspaceDocumentsQueryOptions(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  const rawStatus = options.status === "all" ? undefined : (options.status as StatusFilterInput);
  const resolvedStatus = normaliseStatusFilter(rawStatus) ?? null;
  const search = options.search?.trim() ?? null;
  const sort = options.sort?.trim() ?? null;

  return {
    queryKey: documentsKeys.list(workspaceId, resolvedStatus, search, sort),
    queryFn: ({ signal }: QueryFunctionContext) =>
      listWorkspaceDocuments(
        workspaceId,
        { status: resolvedStatus ?? undefined, search, sort },
        signal,
      ),
    enabled: workspaceId.length > 0,
    placeholderData: (previous: DocumentListResponse | undefined) => previous,
    staleTime: 15_000,
  };
}

export type DocumentListResponse = components["schemas"]["DocumentListResponse"];
export type DocumentRecord = components["schemas"]["DocumentRecord"];
export type DocumentStatus = components["schemas"]["DocumentStatus"];

type RawListDocumentsQuery =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["parameters"]["query"];
type ListDocumentsQuery = RawListDocumentsQuery extends undefined
  ? Record<string, never>
  : RawListDocumentsQuery;

export type StatusFilterInput = DocumentStatus | readonly DocumentStatus[] | null | undefined;

export function normaliseStatusFilter(status: StatusFilterInput) {
  if (status == null) {
    return undefined;
  }
  if (Array.isArray(status)) {
    const filtered = (status as readonly DocumentStatus[]).filter(
      (value): value is DocumentStatus => Boolean(value),
    );
    return filtered.length > 0 ? filtered : undefined;
  }
  return [status as DocumentStatus];
}
