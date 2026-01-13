import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@api/listing";
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


export interface ListWorkspacesOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly q?: string;
  readonly filters?: FilterItem[];
  readonly joinOperator?: FilterJoinOperator;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchWorkspaces(options: ListWorkspacesOptions = {}): Promise<WorkspaceListPage> {
  const { limit, cursor, sort, q, filters, joinOperator, includeTotal, signal } = options;
  const normalizedPageSize = clampPageSize(limit ?? DEFAULT_WORKSPACE_PAGE_SIZE);
  const query = buildListQuery({
    limit: normalizedPageSize,
    cursor: cursor ?? null,
    sort: sort ?? null,
    q,
    filters,
    joinOperator,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/workspaces", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace page payload.");
  }

  return data;
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
  const { data } = await client.PATCH("/api/v1/workspaces/{workspaceId}", {
    params: { path: { workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace payload.");
  }

  return data;
}

export async function deleteWorkspace(workspaceId: string): Promise<void> {
  await client.DELETE("/api/v1/workspaces/{workspaceId}", {
    params: { path: { workspaceId } },
  });
}

export interface ListWorkspaceMembersOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly q?: string;
  readonly filters?: FilterItem[];
  readonly joinOperator?: FilterJoinOperator;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listWorkspaceMembers(
  workspaceId: string,
  options: ListWorkspaceMembersOptions = {},
): Promise<WorkspaceMemberPage> {
  const { limit, cursor, sort, q, filters, joinOperator, includeTotal, signal } = options;
  const normalizedPageSize = clampPageSize(limit ?? DEFAULT_MEMBER_PAGE_SIZE);
  const query = buildListQuery({
    limit: normalizedPageSize,
    cursor: cursor ?? null,
    sort: sort ?? null,
    q,
    filters,
    joinOperator,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/members", {
    params: { path: { workspaceId }, query },
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
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/members", {
    params: { path: { workspaceId } },
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
  const { data } = await client.PUT("/api/v1/workspaces/{workspaceId}/members/{userId}", {
    params: {
      path: {
        workspaceId,
        userId,
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
  await client.DELETE("/api/v1/workspaces/{workspaceId}/members/{userId}", {
    params: {
      path: {
        workspaceId,
        userId,
      },
    },
  });
}

export interface ListWorkspaceRolesOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly q?: string;
  readonly joinOperator?: FilterJoinOperator;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listWorkspaceRoles(options: ListWorkspaceRolesOptions = {}): Promise<RoleListPage> {
  const { limit, cursor, sort, q, joinOperator, includeTotal, signal } = options;
  const normalizedPageSize = clampPageSize(limit ?? DEFAULT_ROLE_PAGE_SIZE);
  const filters: FilterItem[] = [{ id: "scopeType", operator: "eq", value: WORKSPACE_SCOPE }];
  const query = buildListQuery({
    limit: normalizedPageSize,
    cursor: cursor ?? null,
    sort: sort ?? null,
    q,
    filters,
    joinOperator,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/roles", { params: { query }, signal });

  if (!data) {
    throw new Error("Expected workspace role page payload.");
  }

  return data;
}

export async function createWorkspaceRole(_workspaceId: string, payload: RoleCreatePayload) {
  const { data } = await client.POST("/api/v1/roles", { body: payload });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function updateWorkspaceRole(
  _workspaceId: string,
  roleId: string,
  payload: RoleUpdatePayload,
  options: { ifMatch?: string | null } = {},
) {
  const { data } = await client.PATCH("/api/v1/roles/{roleId}", {
    params: { path: { roleId } },
    body: payload,
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function deleteWorkspaceRole(
  _workspaceId: string,
  roleId: string,
  options: { ifMatch?: string | null } = {},
) {
  await client.DELETE("/api/v1/roles/{roleId}", {
    params: { path: { roleId } },
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });
}

export interface ListPermissionsOptions {
  readonly scope?: ScopeType;
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string;
  readonly q?: string;
  readonly joinOperator?: FilterJoinOperator;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listPermissions(options: ListPermissionsOptions = {}): Promise<PermissionListPage> {
  const { scope = WORKSPACE_SCOPE, limit, cursor, sort, q, joinOperator, includeTotal, signal } = options;
  const normalizedPageSize = clampPageSize(limit ?? DEFAULT_PERMISSION_PAGE_SIZE);
  const filters: FilterItem[] = [{ id: "scopeType", operator: "eq", value: scope }];
  const query = buildListQuery({
    limit: normalizedPageSize,
    cursor: cursor ?? null,
    sort: sort ?? null,
    q,
    filters,
    joinOperator,
    includeTotal,
  });

  const { data } = await client.GET("/api/v1/permissions", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected permission page payload.");
  }

  return data;
}

const setDefaultWorkspacePath: PathsWithMethod<paths, "put"> = "/api/v1/workspaces/{workspaceId}/default";

export async function setDefaultWorkspace(workspaceId: string): Promise<void> {
  await client.PUT(setDefaultWorkspacePath, {
    params: { path: { workspaceId } },
  });
}
