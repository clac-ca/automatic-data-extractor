import { del, get, patch, post } from "../../shared/api/client";
import type {
  PermissionDefinition,
  RoleAssignment,
  RoleAssignmentCreatePayload,
  RoleCreatePayload,
  RoleDefinition,
  RoleUpdatePayload,
  UserSummary,
} from "../../shared/api/types";

interface RoleResponse {
  role_id: string;
  slug: string;
  name: string;
  description?: string | null;
  scope_type: "global" | "workspace";
  scope_id?: string | null;
  permissions: string[];
  built_in: boolean;
  editable: boolean;
}

interface RoleAssignmentResponse {
  assignment_id: string;
  principal_id: string;
  principal_type: "user";
  user_id?: string | null;
  user_email?: string | null;
  user_display_name?: string | null;
  role_id: string;
  role_slug: string;
  scope_type: "global" | "workspace";
  scope_id?: string | null;
  created_at: string;
}

function mapRole(payload: RoleResponse): RoleDefinition {
  return {
    id: payload.role_id,
    slug: payload.slug,
    name: payload.name,
    description: payload.description ?? null,
    scope_type: payload.scope_type,
    scope_id: payload.scope_id ?? null,
    permissions: payload.permissions ?? [],
    built_in: payload.built_in,
    editable: payload.editable,
  } satisfies RoleDefinition;
}

function mapAssignment(payload: RoleAssignmentResponse): RoleAssignment {
  return {
    id: payload.assignment_id,
    principal_id: payload.principal_id,
    principal_type: payload.principal_type,
    user_id: payload.user_id ?? null,
    user_email: payload.user_email ?? null,
    user_display_name: payload.user_display_name ?? null,
    role_id: payload.role_id,
    role_slug: payload.role_slug,
    scope_type: payload.scope_type,
    scope_id: payload.scope_id ?? null,
    created_at: payload.created_at,
  } satisfies RoleAssignment;
}

export async function fetchPermissions() {
  return get<PermissionDefinition[]>("/permissions");
}

export async function fetchGlobalRoles() {
  const response = await get<RoleResponse[]>("/roles?scope=global");
  return response.map(mapRole);
}

export async function createGlobalRole(payload: RoleCreatePayload) {
  const response = await post<RoleResponse>("/roles?scope=global", payload);
  return mapRole(response);
}

export async function updateRole(roleId: string, payload: RoleUpdatePayload) {
  const response = await patch<RoleResponse>(`/roles/${roleId}`, payload);
  return mapRole(response);
}

export async function deleteRole(roleId: string) {
  await del(`/roles/${roleId}`);
}

export async function fetchGlobalRoleAssignments(params: { principal_id?: string; role_id?: string } = {}) {
  const query = new URLSearchParams();
  if (params.principal_id) {
    query.set("principal_id", params.principal_id);
  }
  if (params.role_id) {
    query.set("role_id", params.role_id);
  }
  const queryString = query.toString();
  const path = queryString ? `/role-assignments?${queryString}` : "/role-assignments";
  const response = await get<RoleAssignmentResponse[]>(path);
  return response.map(mapAssignment);
}

export async function createGlobalRoleAssignment(payload: RoleAssignmentCreatePayload) {
  const response = await post<RoleAssignmentResponse>("/role-assignments", payload);
  return mapAssignment(response);
}

export async function deleteRoleAssignment(assignmentId: string, workspaceId?: string) {
  if (workspaceId) {
    await del(`/workspaces/${workspaceId}/role-assignments/${assignmentId}`);
    return;
  }
  await del(`/role-assignments/${assignmentId}`);
}

export async function fetchWorkspaceRoleAssignments(
  workspaceId: string,
  params: { principal_id?: string; role_id?: string } = {},
) {
  const query = new URLSearchParams();
  if (params.principal_id) {
    query.set("principal_id", params.principal_id);
  }
  if (params.role_id) {
    query.set("role_id", params.role_id);
  }
  const queryString = query.toString();
  const path = queryString
    ? `/workspaces/${workspaceId}/role-assignments?${queryString}`
    : `/workspaces/${workspaceId}/role-assignments`;
  const response = await get<RoleAssignmentResponse[]>(path);
  return response.map(mapAssignment);
}

export async function createWorkspaceRoleAssignment(workspaceId: string, payload: RoleAssignmentCreatePayload) {
  const response = await post<RoleAssignmentResponse>(`/workspaces/${workspaceId}/role-assignments`, payload);
  return mapAssignment(response);
}

export async function fetchUsers() {
  return get<UserSummary[]>("/users");
}
