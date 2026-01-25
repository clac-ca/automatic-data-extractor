import { resolveApiUrl } from "@/api/client";

export function documentsChangesStreamUrl(
  workspaceId: string,
  options: { includeRows?: boolean } = {},
) {
  const params = new URLSearchParams();
  if (options.includeRows) {
    params.set("includeRows", "true");
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/changes/stream${suffix}`);
}
