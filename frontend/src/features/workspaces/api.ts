import { get, post } from "../../shared/api/client";
import type { WorkspaceCreatePayload, WorkspaceProfile } from "../../shared/types/workspaces";

interface WorkspaceApiProfile {
  workspace_id?: string;
  id?: string;
  name: string;
  slug: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
}

function normalizeWorkspaceProfile(api: WorkspaceApiProfile): WorkspaceProfile {
  return {
    id: api.workspace_id ?? api.id ?? "",
    name: api.name,
    slug: api.slug,
    roles: api.roles,
    permissions: api.permissions,
    is_default: api.is_default,
  };
}

export async function fetchWorkspaces(signal?: AbortSignal) {
  const response = await get<WorkspaceApiProfile[]>("/workspaces", { signal });
  return response
    .map((workspace) => normalizeWorkspaceProfile(workspace))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export async function createWorkspace(payload: WorkspaceCreatePayload) {
  const workspace = await post<WorkspaceApiProfile>("/workspaces", payload);
  return normalizeWorkspaceProfile(workspace);
}
