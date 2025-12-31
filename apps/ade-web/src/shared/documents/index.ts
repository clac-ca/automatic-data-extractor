import { client } from "@shared/api/client";
import type { components } from "@schema";

export type DocumentSheet = components["schemas"]["DocumentSheet"];

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

export * from "./uploads";
export * from "./tags";
export * from "./changes";
