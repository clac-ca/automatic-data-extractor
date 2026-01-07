import { resolveApiUrl } from "@api/client";

export function documentsChangesStreamUrl(workspaceId: string, cursor: string) {
  const params = new URLSearchParams({ cursor });
  return resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/changes/stream?${params.toString()}`);
}
