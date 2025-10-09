import { del, get, post, put, type ApiClientOptions } from "../../shared/api/client";
import type {
  CreateWorkspacePayload,
  DocumentTypeDetailResponse,
  RoleDefinition,
  WorkspaceMember,
  WorkspaceMemberCreatePayload,
  WorkspaceMemberRolesUpdatePayload,
  WorkspaceProfile,
} from "../../shared/api/types";

interface WorkspaceProfileResponse {
  workspace_id: string;
  name: string;
  slug: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
}

interface WorkspaceMemberResponse {
  workspace_membership_id: string;
  workspace_id: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
  user: {
    user_id: string;
    email: string;
    is_active: boolean;
    is_service_account: boolean;
    display_name?: string | null;
    roles?: string[];
    permissions?: string[];
  };
}

interface WorkspaceRoleResponse {
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

function mapWorkspaceProfile(payload: WorkspaceProfileResponse): WorkspaceProfile {
  return {
    id: payload.workspace_id,
    name: payload.name,
    slug: payload.slug,
    roles: payload.roles ?? [],
    permissions: payload.permissions ?? [],
    is_default: payload.is_default,
  } satisfies WorkspaceProfile;
}

function mapWorkspaceMember(payload: WorkspaceMemberResponse): WorkspaceMember {
  return {
    id: payload.workspace_membership_id,
    workspace_id: payload.workspace_id,
    roles: payload.roles ?? [],
    permissions: payload.permissions ?? [],
    is_default: payload.is_default,
    user: {
      user_id: payload.user.user_id,
      email: payload.user.email,
      is_active: payload.user.is_active,
      is_service_account: payload.user.is_service_account,
      display_name: payload.user.display_name ?? null,
      roles: payload.user.roles ?? [],
      permissions: payload.user.permissions ?? [],
    },
  } satisfies WorkspaceMember;
}

function mapWorkspaceRole(payload: WorkspaceRoleResponse): RoleDefinition {
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

export async function fetchWorkspaces(options?: ApiClientOptions) {
  const response = await get<WorkspaceProfileResponse[]>("/workspaces", options);
  return response.map(mapWorkspaceProfile);
}

export async function fetchDocumentType(workspaceId: string, documentTypeId: string, options?: ApiClientOptions) {
  return get<DocumentTypeDetailResponse>(`/workspaces/${workspaceId}/document-types/${documentTypeId}`, options);
}

export async function createWorkspace(payload: CreateWorkspacePayload) {
  const response = await post<WorkspaceProfileResponse>("/workspaces", payload);
  return mapWorkspaceProfile(response);
}

export async function fetchWorkspaceMembers(workspaceId: string, options?: ApiClientOptions) {
  const response = await get<WorkspaceMemberResponse[]>(`/workspaces/${workspaceId}/members`, options);
  return response.map(mapWorkspaceMember);
}

export async function fetchWorkspaceRoles(workspaceId: string, options?: ApiClientOptions) {
  const response = await get<WorkspaceRoleResponse[]>(`/workspaces/${workspaceId}/roles`, options);
  return response.map(mapWorkspaceRole);
}

export async function addWorkspaceMember(workspaceId: string, payload: WorkspaceMemberCreatePayload) {
  const response = await post<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members`, payload);
  return mapWorkspaceMember(response);
}

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  membershipId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
) {
  const response = await put<WorkspaceMemberResponse>(
    `/workspaces/${workspaceId}/members/${membershipId}/roles`,
    payload,
  );
  return mapWorkspaceMember(response);
}

export async function removeWorkspaceMember(workspaceId: string, membershipId: string) {
  await del(`/workspaces/${workspaceId}/members/${membershipId}`);
}
