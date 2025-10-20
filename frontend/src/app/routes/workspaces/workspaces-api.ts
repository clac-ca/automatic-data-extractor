import { useQuery } from "@tanstack/react-query";

import { del, get, patch, post, put } from "@shared/api";
import type {
  WorkspaceApiProfile,
  WorkspaceCreatePayload,
  WorkspaceProfile,
  WorkspaceUpdatePayload,
} from "@schema/workspaces";
import type { WorkspaceMember } from "@schema/workspace-members";
import type {
  RoleCreatePayload,
  RoleDefinition,
  RoleUpdatePayload,
  PermissionDefinition,
} from "@schema/roles";

function normalizeWorkspaceProfile(api: WorkspaceApiProfile): WorkspaceProfile {
  return {
    id: api.workspace_id,
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

export function updateWorkspace(workspaceId: string, payload: WorkspaceUpdatePayload) {
  return patch<WorkspaceApiProfile>(`/workspaces/${workspaceId}`, payload).then(normalizeWorkspaceProfile);
}

export interface AddWorkspaceMemberPayload {
  readonly user_id: string;
  readonly role_ids?: readonly string[];
}

export function listWorkspaceMembers(workspaceId: string, signal?: AbortSignal) {
  return get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`, { signal });
}

export function addWorkspaceMember(workspaceId: string, payload: AddWorkspaceMemberPayload) {
  return post<WorkspaceMember>(`/workspaces/${workspaceId}/members`, {
    user_id: payload.user_id,
    role_ids: payload.role_ids ?? [],
  });
}

export function updateWorkspaceMemberRoles(
  workspaceId: string,
  membershipId: string,
  roleIds: readonly string[],
) {
  return put<WorkspaceMember>(`/workspaces/${workspaceId}/members/${membershipId}/roles`, {
    role_ids: roleIds,
  });
}

export function removeWorkspaceMember(workspaceId: string, membershipId: string) {
  return del(`/workspaces/${workspaceId}/members/${membershipId}`).then(() => undefined);
}

export function listWorkspaceRoles(workspaceId: string, signal?: AbortSignal) {
  return get<RoleDefinition[]>(`/workspaces/${workspaceId}/roles`, { signal });
}

export function createWorkspaceRole(workspaceId: string, payload: RoleCreatePayload) {
  return post<RoleDefinition>(`/workspaces/${workspaceId}/roles`, payload);
}

export function updateWorkspaceRole(
  workspaceId: string,
  roleId: string,
  payload: RoleUpdatePayload,
) {
  return put<RoleDefinition>(`/workspaces/${workspaceId}/roles/${roleId}`, payload);
}

export function deleteWorkspaceRole(workspaceId: string, roleId: string) {
  return del(`/workspaces/${workspaceId}/roles/${roleId}`).then(() => undefined);
}

export function listPermissions(signal?: AbortSignal) {
  return get<PermissionDefinition[]>("/permissions", { signal });
}

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: () => [...workspacesKeys.all(), "list"] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "members"] as const,
  roles: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "roles"] as const,
  permissions: () => ["permissions"] as const,
};

export interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
}

export function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  return {
    queryKey: workspacesKeys.list(),
    queryFn: ({ signal }: { signal?: AbortSignal }) => fetchWorkspaces(signal),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  };
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  return useQuery<WorkspaceProfile[]>(workspacesListQueryOptions(options));
}
