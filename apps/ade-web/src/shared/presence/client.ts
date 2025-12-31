import { resolveApiUrl } from "@shared/api/client";

export function resolveWebSocketUrl(path: string) {
  const resolved = resolveApiUrl(path);
  if (resolved.startsWith("https://")) {
    return `wss://${resolved.slice("https://".length)}`;
  }
  if (resolved.startsWith("http://")) {
    return `ws://${resolved.slice("http://".length)}`;
  }
  if (resolved.startsWith("/")) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${resolved}`;
  }
  return resolved;
}

export function presenceSocketUrl(workspaceId: string) {
  return resolveWebSocketUrl(`/api/v1/workspaces/${workspaceId}/presence`);
}
