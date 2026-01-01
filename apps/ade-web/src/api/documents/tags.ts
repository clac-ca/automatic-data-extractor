import { client } from "@api/client";
import type { ListQueryParams } from "@api/listing";
import type { components } from "@schema";

type DocumentRecord = components["schemas"]["DocumentOut"];
type TagCatalogPage = components["schemas"]["TagCatalogPage"];
type TagCatalogQuery = Pick<ListQueryParams, "page" | "perPage" | "sort" | "q">;

export async function replaceDocumentTags(
  workspaceId: string,
  documentId: string,
  tags: readonly string[],
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/tags",
    {
      params: { path: { workspaceId, documentId } },
      body: { tags: [...tags] },
      signal,
    },
  );

  if (!data) {
    throw new Error("Expected document payload.");
  }

  return data as DocumentRecord;
}

export async function patchDocumentTags(
  workspaceId: string,
  documentId: string,
  payload: { add?: readonly string[] | null; remove?: readonly string[] | null },
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const body = {
    add: payload.add ? [...payload.add] : payload.add,
    remove: payload.remove ? [...payload.remove] : payload.remove,
  };
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspaceId}/documents/{documentId}/tags",
    {
      params: { path: { workspaceId, documentId } },
      body,
      signal,
    },
  );

  if (!data) {
    throw new Error("Expected document payload.");
  }

  return data as DocumentRecord;
}

export async function patchDocumentTagsBatch(
  workspaceId: string,
  documentIds: string[],
  payload: { add?: readonly string[] | null; remove?: readonly string[] | null },
  signal?: AbortSignal,
): Promise<DocumentRecord[]> {
  const body = {
    document_ids: documentIds,
    add: payload.add ? [...payload.add] : payload.add,
    remove: payload.remove ? [...payload.remove] : payload.remove,
  };
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/documents/batch/tags", {
    params: { path: { workspaceId } },
    body,
    signal,
  });

  if (!data) {
    throw new Error("Expected updated document records.");
  }

  return (data.documents ?? []) as DocumentRecord[];
}

export async function fetchTagCatalog(
  workspaceId: string,
  query: TagCatalogQuery = {},
  signal?: AbortSignal,
): Promise<TagCatalogPage> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/tags", {
    params: {
      path: { workspaceId },
      query,
    },
    signal,
  });

  if (!data) {
    throw new Error("Expected tag catalog payload.");
  }

  return data as TagCatalogPage;
}
