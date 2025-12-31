import { clampPageSize, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE } from "@api/pagination";
import { client } from "@api/client";
import type { paths, ScopeType } from "@schema";
import type { PathsWithMethod } from "openapi-typescript-helpers";

import type {
  PermissionListPage,
  RoleCreatePayload,
  RoleListPage,
  RoleUpdatePayload,
  WorkspaceCreatePayload,
  WorkspaceListPage,
  WorkspaceMember,
  WorkspaceMemberCreatePayload,
  WorkspaceMemberPage,
  WorkspaceMemberRolesUpdatePayload,
  WorkspaceProfile,
  WorkspaceUpdatePayload,
} from "@schema/workspaces";

export const DEFAULT_WORKSPACE_PAGE_SIZE = MAX_PAGE_SIZE;
export const DEFAULT_MEMBER_PAGE_SIZE = DEFAULT_PAGE_SIZE;
export const DEFAULT_ROLE_PAGE_SIZE = DEFAULT_PAGE_SIZE;
export const DEFAULT_PERMISSION_PAGE_SIZE = DEFAULT_PAGE_SIZE;

const WORKSPACE_SCOPE: ScopeType = "workspace";

type ListWorkspacesQuery = paths["/api/v1/workspaces"]["get"]["parameters"]["query"];
type ListWorkspaceMembersQuery = paths["/api/v1/workspaces/{workspace_id}/members"]["get"]["parameters"]["query"];
type ListRolesQuery = paths["/api/v1/rbac/roles"]["get"]["parameters"]["query"];
type ListPermissionsQuery = paths["/api/v1/rbac/permissions"]["get"]["parameters"]["query"];

export interface ListWorkspacesOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchWorkspaces(options: ListWorkspacesOptions = {}): Promise<WorkspaceListPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListWorkspacesQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }

  const normalizedPageSize = clampPageSize(pageSize ?? DEFAULT_WORKSPACE_PAGE_SIZE);
  if (normalizedPageSize) {
    query.page_size = normalizedPageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace page payload.");
  }

  const sorted = [...data.items].sort((a, b) => a.name.localeCompare(b.name));
  return { ...data, items: sorted };
}

export async function createWorkspace(payload: WorkspaceCreatePayload): Promise<WorkspaceProfile> {
  const { data } = await client.POST("/api/v1/workspaces", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace payload.");
  }

  return data;
}

export async function updateWorkspace(workspaceId: string, payload: WorkspaceUpdatePayload): Promise<WorkspaceProfile> {
  const { data } = await client.PATCH("/api/v1/workspaces/{workspace_id}", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace payload.");
  }

  return data;
}

export async function deleteWorkspace(workspaceId: string): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspace_id}", {
    params: { path: { workspace_id: workspaceId } },
  });
}

export interface ListWorkspaceMembersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listWorkspaceMembers(
  workspaceId: string,
  options: ListWorkspaceMembersOptions = {},
): Promise<WorkspaceMemberPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListWorkspaceMembersQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }

  const normalizedPageSize = clampPageSize(pageSize ?? DEFAULT_MEMBER_PAGE_SIZE);
  if (normalizedPageSize) {
    query.page_size = normalizedPageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace member page payload.");
  }

  return data;
}

export async function addWorkspaceMember(
  workspaceId: string,
  payload: WorkspaceMemberCreatePayload,
): Promise<WorkspaceMember> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data as WorkspaceMember;
}

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  userId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
): Promise<WorkspaceMember> {
  const { data } = await client.PUT("/api/v1/workspaces/{workspace_id}/members/{user_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        user_id: userId,
      },
    },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data as WorkspaceMember;
}

export async function removeWorkspaceMember(workspaceId: string, userId: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/members/{user_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        user_id: userId,
      },
    },
  });
}

export interface ListWorkspaceRolesOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listWorkspaceRoles(options: ListWorkspaceRolesOptions = {}): Promise<RoleListPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListRolesQuery = { scope: WORKSPACE_SCOPE };

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }

  const normalizedPageSize = clampPageSize(pageSize ?? DEFAULT_ROLE_PAGE_SIZE);
  if (normalizedPageSize) {
    query.page_size = normalizedPageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/rbac/roles", { params: { query }, signal });

  if (!data) {
    throw new Error("Expected workspace role page payload.");
  }

  return data;
}

export async function createWorkspaceRole(_workspaceId: string, payload: RoleCreatePayload) {
  const { data } = await client.POST("/api/v1/rbac/roles", { body: payload });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function updateWorkspaceRole(_workspaceId: string, roleId: string, payload: RoleUpdatePayload) {
  const { data } = await client.PATCH("/api/v1/rbac/roles/{role_id}", {
    params: { path: { role_id: roleId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function deleteWorkspaceRole(_workspaceId: string, roleId: string) {
  await client.DELETE("/api/v1/rbac/roles/{role_id}", {
    params: { path: { role_id: roleId } },
  });
}

export interface ListPermissionsOptions {
  readonly scope?: ScopeType;
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listPermissions(options: ListPermissionsOptions = {}): Promise<PermissionListPage> {
  const { scope = WORKSPACE_SCOPE, page, pageSize, includeTotal, signal } = options;
  const query: ListPermissionsQuery = { scope };

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }

  const normalizedPageSize = clampPageSize(pageSize ?? DEFAULT_PERMISSION_PAGE_SIZE);
  if (normalizedPageSize) {
    query.page_size = normalizedPageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/rbac/permissions", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected permission page payload.");
  }

  return data;
}

const setDefaultWorkspacePath: PathsWithMethod<paths, "put"> = "/api/v1/workspaces/{workspace_id}/default";

export async function setDefaultWorkspace(workspaceId: string): Promise<void> {
  await client.PUT(setDefaultWorkspacePath, {
    params: { path: { workspace_id: workspaceId } },
  });
}
