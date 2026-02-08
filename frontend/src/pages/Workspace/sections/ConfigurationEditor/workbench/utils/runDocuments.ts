import { client } from "@/api/client";
import type { components } from "@/types";

export type WorkbenchDocumentRow = components["schemas"]["DocumentListRow"];

export async function fetchRecentDocuments(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<WorkbenchDocumentRow[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents", {
    params: {
      path: { workspaceId },
      query: { sort: '[{"id":"createdAt","desc":true}]', limit: 50 },
    },
    signal,
  });
  return data?.items ?? [];
}

export function formatDocumentTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
