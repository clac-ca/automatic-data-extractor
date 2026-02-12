import { buildListQuery, type FilterItem, type FilterJoinOperator } from "@/api/listing";
import { clampPageSize, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE } from "@/api/pagination";
import { client } from "@/api/client";
import type { paths, ScopeType } from "@/types";
import type { PathsWithMethod } from "openapi-typescript-helpers";

import type {
  PermissionListPage,
  RoleCreatePayload,
  RoleListPage,
  RoleUpdatePayload,
  WorkspaceCreatePayload,
  WorkspaceListPage,
  WorkspaceProfile,
  WorkspaceUpdatePayload,
} from "@/types/workspaces";
import type { WorkspaceMember, WorkspaceMemberCreatePayload, WorkspaceMemberPage, WorkspaceMemberRolesUpdatePayload } from "@/types/workspaces";
import type { components } from "@/types";

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

type RoleAssignmentOut = components["schemas"]["RoleAssignmentOut"];
type RoleAssignmentPage = components["schemas"]["RoleAssignmentPage"];

export async function listWorkspaceRoleAssignmentsRaw(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<RoleAssignmentOut[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/roleAssignments", {
    params: {
      path: { workspaceId },
    },
    signal: options.signal,
  });

  if (!data?.items) {
    throw new Error("Expected workspace role assignments payload.");
  }

  return (data as RoleAssignmentPage).items;
}

function toWorkspaceMemberPage(assignments: RoleAssignmentOut[]): WorkspaceMemberPage {
  const byUser = new Map<
    string,
    {
      role_ids: string[];
      role_slugs: string[];
      created_at: string;
      display_name: string | null;
      email: string | null;
    }
  >();

  for (const assignment of assignments) {
    if (assignment.principal_type !== "user") {
      continue;
    }
    const userId = assignment.principal_id;
    const existing = byUser.get(userId);
    if (!existing) {
      byUser.set(userId, {
        role_ids: [assignment.role_id],
        role_slugs: [assignment.role_slug],
        created_at: assignment.created_at,
        display_name: assignment.principal_display_name ?? null,
        email: assignment.principal_email ?? null,
      });
      continue;
    }
    if (!existing.role_ids.includes(assignment.role_id)) {
      existing.role_ids.push(assignment.role_id);
    }
    if (!existing.role_slugs.includes(assignment.role_slug)) {
      existing.role_slugs.push(assignment.role_slug);
    }
    if (assignment.created_at < existing.created_at) {
      existing.created_at = assignment.created_at;
    }
    existing.display_name = existing.display_name ?? assignment.principal_display_name ?? null;
    existing.email = existing.email ?? assignment.principal_email ?? null;
  }

  const items: WorkspaceMember[] = Array.from(byUser.entries()).map(([userId, value]) => ({
    user_id: userId,
    role_ids: value.role_ids,
    role_slugs: value.role_slugs,
    created_at: value.created_at,
    user: value.email
      ? ({
          id: userId,
          email: value.email,
          display_name: value.display_name,
        } as WorkspaceMember["user"])
      : undefined,
  }));

  return {
    items,
    meta: {
      limit: items.length || 1,
      hasMore: false,
      nextCursor: null,
      totalIncluded: true,
      totalCount: items.length,
      changesCursor: "0",
    },
    facets: null,
  };
}

async function findWorkspaceMemberByUserId(
  workspaceId: string,
  userId: string,
): Promise<WorkspaceMember | null> {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const page = toWorkspaceMemberPage(assignments);
  return page.items.find((item) => item.user_id === userId) ?? null;
}

export async function listWorkspaceMembers(
  workspaceId: string,
  options: ListWorkspaceMembersOptions = {},
): Promise<WorkspaceMemberPage> {
  void options;
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId, { signal: options.signal });
  return toWorkspaceMemberPage(assignments);
}

export async function addWorkspaceMember(
  workspaceId: string,
  payload: WorkspaceMemberCreatePayload,
): Promise<WorkspaceMember> {
  if (payload.role_ids.length === 0) {
    throw new Error("Select at least one role for this member.");
  }

  await Promise.all(
    payload.role_ids.map(async (roleId) => {
      await client.POST("/api/v1/workspaces/{workspaceId}/roleAssignments", {
        params: { path: { workspaceId } },
        body: {
          principal_type: "user",
          principal_id: payload.user_id,
          role_id: roleId,
        },
      });
    }),
  );

  const member = await findWorkspaceMemberByUserId(workspaceId, payload.user_id);
  if (!member) {
    throw new Error("Expected workspace member payload.");
  }
  return member;
}

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  userId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
): Promise<WorkspaceMember> {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const current = assignments.filter(
    (assignment) => assignment.principal_type === "user" && assignment.principal_id === userId,
  );
  const desiredRoleIds = new Set(payload.role_ids);
  const toDelete = current.filter((assignment) => !desiredRoleIds.has(assignment.role_id));
  const existingRoleIds = new Set(current.map((assignment) => assignment.role_id));
  const toAdd = payload.role_ids.filter((roleId) => !existingRoleIds.has(roleId));

  await Promise.all(
    toAdd.map(async (roleId) => {
      await client.POST("/api/v1/workspaces/{workspaceId}/roleAssignments", {
        params: { path: { workspaceId } },
        body: {
          principal_type: "user",
          principal_id: userId,
          role_id: roleId,
        },
      });
    }),
  );

  await Promise.all(
    toDelete.map(async (assignment) => {
      await client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
        params: { path: { assignmentId: assignment.id } },
      });
    }),
  );

  const member = await findWorkspaceMemberByUserId(workspaceId, userId);
  if (!member) {
    if (payload.role_ids.length === 0) {
      return {
        user_id: userId,
        role_ids: [],
        role_slugs: [],
        created_at: new Date().toISOString(),
      };
    }
    throw new Error("Expected workspace member payload.");
  }
  return member;
}

export async function removeWorkspaceMember(workspaceId: string, userId: string) {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const userAssignments = assignments.filter(
    (assignment) => assignment.principal_type === "user" && assignment.principal_id === userId,
  );
  await Promise.all(
    userAssignments.map(async (assignment) => {
      await client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
        params: { path: { assignmentId: assignment.id } },
      });
    }),
  );
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
