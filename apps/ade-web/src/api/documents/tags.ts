import { client } from "@api/client";
import type { components, paths } from "@schema";

type DocumentRecord = components["schemas"]["DocumentOut"];
type TagCatalogPage = components["schemas"]["TagCatalogPage"];
type TagCatalogQuery =
  paths["/api/v1/workspaces/{workspace_id}/tags"]["get"]["parameters"]["query"];

export async function replaceDocumentTags(
  workspaceId: string,
  documentId: string,
  tags: readonly string[],
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/tags",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
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
    "/api/v1/workspaces/{workspace_id}/documents/{document_id}/tags",
    {
      params: { path: { workspace_id: workspaceId, document_id: documentId } },
      body,
      signal,
    },
  );

  if (!data) {
    throw new Error("Expected document payload.");
  }

  return data as DocumentRecord;
}

export async function fetchTagCatalog(
  workspaceId: string,
  query: TagCatalogQuery = {},
  signal?: AbortSignal,
): Promise<TagCatalogPage> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/tags", {
    params: {
      path: { workspace_id: workspaceId },
      query,
    },
    signal,
  });

  if (!data) {
    throw new Error("Expected tag catalog payload.");
  }

  return data as TagCatalogPage;
}
