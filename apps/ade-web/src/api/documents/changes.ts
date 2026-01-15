import { resolveApiUrl } from "@/api/client";

export function documentsChangesStreamUrl(
  workspaceId: string,
  cursor: string,
  options: { includeRows?: boolean } = {},
) {
  const params = new URLSearchParams({ cursor });
  if (options.includeRows) {
    params.set("includeRows", "true");
  }
  return resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/changes/stream?${params.toString()}`);
}
