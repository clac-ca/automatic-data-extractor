import { client, resolveApiUrl } from "@/api/client";
import type { components } from "@/types";

export type DocumentChangeEntry = components["schemas"]["DocumentChangeEntry"];
export type DocumentChangeDeltaResponse = components["schemas"]["DocumentChangeDeltaResponse"];

export type DocumentChangeNotification = {
  documentId: string;
  op: DocumentChangeEntry["op"];
  id?: DocumentChangeEntry["id"] | null;
};

export function documentsStreamUrl(workspaceId: string) {
  return resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/stream`);
}

export async function fetchWorkspaceDocumentsDelta(
  workspaceId: string,
  options: { since: string; limit?: number },
  signal?: AbortSignal,
): Promise<DocumentChangeDeltaResponse> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents/delta", {
    params: { path: { workspaceId }, query: { since: options.since, limit: options.limit } },
    signal,
  });
  if (!data) throw new Error("Expected document change delta payload.");
  return data;
}
