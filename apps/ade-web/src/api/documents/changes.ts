import { resolveWebSocketUrl } from "@api/presence/client";

export function documentsChangesSocketUrl(workspaceId: string) {
  return resolveWebSocketUrl(`/api/v1/workspaces/${workspaceId}/documents/changes/ws`);
}
