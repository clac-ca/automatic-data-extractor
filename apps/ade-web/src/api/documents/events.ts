import { resolveApiUrl } from "@/api/client";
import type { DocumentListRow } from "./api";

export type DocumentEventEntry = {
  cursor?: string | null;
  type: "document.changed" | "document.deleted";
  documentId?: string | null;
  occurredAt?: string | null;
  documentVersion?: number | null;
  row?: DocumentListRow | null;
};

export function documentsEventsStreamUrl(
  workspaceId: string,
  options: { includeRows?: boolean } = {},
) {
  const params = new URLSearchParams();
  if (options.includeRows) {
    params.set("include", "rows");
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/events/stream${suffix}`);
}
