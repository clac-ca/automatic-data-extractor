import type { SessionEnvelope } from "../../../shared/api/types";

export function resolveSessionDestination(session?: SessionEnvelope | null, fallback: string = "/workspaces") {
  if (!session) {
    return fallback;
  }

  if (session.return_to) {
    return session.return_to;
  }

  const preferredWorkspace = session.user.preferred_workspace_id ?? undefined;
  if (preferredWorkspace) {
    return `/workspaces/${preferredWorkspace}`;
  }

  return fallback;
}
