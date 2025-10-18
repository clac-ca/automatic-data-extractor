import { del, get, patch, post, put } from "../../../shared/api/client";
import type { WorkspaceCreatePayload, WorkspaceProfile } from "../../../shared/types/workspaces";
import type { WorkspaceMember } from "../../../shared/types/workspace-members";
import type {
  RoleCreatePayload,
  RoleDefinition,
  RoleUpdatePayload,
  PermissionDefinition,
} from "../../../shared/types/roles";

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

export interface WorkspaceUpdatePayload {
  readonly name?: string | null;
  readonly slug?: string | null;
  readonly settings?: Record<string, unknown> | null;
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
  return del(`/workspaces/${workspaceId}/members/${membershipId}`);
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
  return del(`/workspaces/${workspaceId}/roles/${roleId}`);
}

export function listPermissions(signal?: AbortSignal) {
  return get<PermissionDefinition[]>("/permissions", { signal });
}
