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
  WorkspacePrincipal,
  WorkspacePrincipalPage,
  WorkspacePrincipalType,
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

export interface ListWorkspacePrincipalsOptions {
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

function toWorkspacePrincipalPage(assignments: RoleAssignmentOut[]): WorkspacePrincipalPage {
  const byPrincipal = new Map<string, WorkspacePrincipal>();

  const keyFor = (principalType: WorkspacePrincipalType, principalId: string) =>
    `${principalType}:${principalId}`;

  for (const assignment of assignments) {
    const principalType = assignment.principal_type as WorkspacePrincipalType;
    const key = keyFor(principalType, assignment.principal_id);
    const existing = byPrincipal.get(key);
    if (!existing) {
      byPrincipal.set(key, {
        principal_type: principalType,
        principal_id: assignment.principal_id,
        role_ids: [assignment.role_id],
        role_slugs: [assignment.role_slug],
        created_at: assignment.created_at,
        principal_display_name: assignment.principal_display_name ?? null,
        principal_email: assignment.principal_email ?? null,
        principal_slug: assignment.principal_slug ?? null,
      });
      continue;
    }
    const roleIds = existing.role_ids.includes(assignment.role_id)
      ? existing.role_ids
      : [...existing.role_ids, assignment.role_id];
    const roleSlugs = existing.role_slugs.includes(assignment.role_slug)
      ? existing.role_slugs
      : [...existing.role_slugs, assignment.role_slug];
    byPrincipal.set(key, {
      ...existing,
      role_ids: roleIds,
      role_slugs: roleSlugs,
      created_at:
        assignment.created_at < existing.created_at ? assignment.created_at : existing.created_at,
      principal_display_name: existing.principal_display_name ?? assignment.principal_display_name ?? null,
      principal_email: existing.principal_email ?? assignment.principal_email ?? null,
      principal_slug: existing.principal_slug ?? assignment.principal_slug ?? null,
    });
  }

  const items = Array.from(byPrincipal.values()).sort((left, right) => {
    const leftLabel =
      left.principal_display_name ?? left.principal_email ?? left.principal_slug ?? left.principal_id;
    const rightLabel =
      right.principal_display_name ??
      right.principal_email ??
      right.principal_slug ??
      right.principal_id;
    return leftLabel.localeCompare(rightLabel);
  });

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

async function findWorkspacePrincipal(
  workspaceId: string,
  principalType: WorkspacePrincipalType,
  principalId: string,
): Promise<WorkspacePrincipal | null> {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const page = toWorkspacePrincipalPage(assignments);
  return (
    page.items.find(
      (item) => item.principal_type === principalType && item.principal_id === principalId,
    ) ?? null
  );
}

export async function listWorkspacePrincipals(
  workspaceId: string,
  options: ListWorkspacePrincipalsOptions = {},
): Promise<WorkspacePrincipalPage> {
  void options;
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId, { signal: options.signal });
  return toWorkspacePrincipalPage(assignments);
}

export async function createWorkspaceRoleAssignment(
  workspaceId: string,
  payload: {
    readonly principal_type: WorkspacePrincipalType;
    readonly principal_id: string;
    readonly role_id: string;
  },
) {
  const { data } = await client.POST("/api/v1/workspaces/{workspaceId}/roleAssignments", {
    params: { path: { workspaceId } },
    body: payload,
  });
  if (!data) {
    throw new Error("Expected workspace role assignment payload.");
  }
  return data as RoleAssignmentOut;
}

export async function addWorkspacePrincipalRoles(
  workspaceId: string,
  payload: {
    readonly principal_type: WorkspacePrincipalType;
    readonly principal_id: string;
    readonly role_ids: readonly string[];
  },
): Promise<WorkspacePrincipal> {
  if (payload.role_ids.length === 0) {
    throw new Error("Select at least one role for this principal.");
  }

  await Promise.all(
    payload.role_ids.map((roleId) =>
      createWorkspaceRoleAssignment(workspaceId, {
        principal_type: payload.principal_type,
        principal_id: payload.principal_id,
        role_id: roleId,
      }),
    ),
  );

  const principal = await findWorkspacePrincipal(
    workspaceId,
    payload.principal_type,
    payload.principal_id,
  );
  if (!principal) {
    throw new Error("Expected workspace principal payload.");
  }
  return principal;
}

export async function updateWorkspacePrincipalRoles(
  workspaceId: string,
  principalType: WorkspacePrincipalType,
  principalId: string,
  payload: { readonly role_ids: readonly string[] },
): Promise<WorkspacePrincipal | null> {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const current = assignments.filter(
    (assignment) =>
      assignment.principal_type === principalType && assignment.principal_id === principalId,
  );
  const desiredRoleIds = new Set(payload.role_ids);
  const toDelete = current.filter((assignment) => !desiredRoleIds.has(assignment.role_id));
  const existingRoleIds = new Set(current.map((assignment) => assignment.role_id));
  const toAdd = payload.role_ids.filter((roleId) => !existingRoleIds.has(roleId));

  await Promise.all(
    toAdd.map((roleId) =>
      createWorkspaceRoleAssignment(workspaceId, {
        principal_type: principalType,
        principal_id: principalId,
        role_id: roleId,
      }),
    ),
  );

  await Promise.all(
    toDelete.map((assignment) =>
      client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
        params: {
          path: { assignmentId: assignment.id },
          header: { "If-Match": "*" },
        },
      }),
    ),
  );

  return findWorkspacePrincipal(workspaceId, principalType, principalId);
}

export async function removeWorkspacePrincipal(
  workspaceId: string,
  principalType: WorkspacePrincipalType,
  principalId: string,
) {
  const assignments = await listWorkspaceRoleAssignmentsRaw(workspaceId);
  const principalAssignments = assignments.filter(
    (assignment) =>
      assignment.principal_type === principalType && assignment.principal_id === principalId,
  );
  await Promise.all(
    principalAssignments.map((assignment) =>
      client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
        params: {
          path: { assignmentId: assignment.id },
          header: { "If-Match": "*" },
        },
      }),
    ),
  );
}

export type ListWorkspaceMembersOptions = ListWorkspacePrincipalsOptions;

export async function listWorkspaceMembers(
  workspaceId: string,
  options: ListWorkspaceMembersOptions = {},
): Promise<WorkspaceMemberPage> {
  const principalPage = await listWorkspacePrincipals(workspaceId, options);
  const items: WorkspaceMember[] = principalPage.items
    .filter((principal) => principal.principal_type === "user")
    .map((principal) => ({
      user_id: principal.principal_id,
      role_ids: principal.role_ids,
      role_slugs: principal.role_slugs,
      created_at: principal.created_at,
      user: principal.principal_email
        ? ({
            id: principal.principal_id,
            email: principal.principal_email,
            display_name: principal.principal_display_name ?? null,
          } as WorkspaceMember["user"])
        : undefined,
    }));

  return {
    items,
    meta: {
      ...principalPage.meta,
      totalCount: items.length,
    },
    facets: principalPage.facets,
  };
}

export async function addWorkspaceMember(
  workspaceId: string,
  payload: WorkspaceMemberCreatePayload,
): Promise<WorkspaceMember> {
  const principal = await addWorkspacePrincipalRoles(workspaceId, {
    principal_type: "user",
    principal_id: payload.user_id,
    role_ids: payload.role_ids,
  });
  return {
    user_id: principal.principal_id,
    role_ids: principal.role_ids,
    role_slugs: principal.role_slugs,
    created_at: principal.created_at,
    user: principal.principal_email
      ? ({
          id: principal.principal_id,
          email: principal.principal_email,
          display_name: principal.principal_display_name ?? null,
        } as WorkspaceMember["user"])
      : undefined,
  };
}

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  userId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
): Promise<WorkspaceMember> {
  const principal = await updateWorkspacePrincipalRoles(workspaceId, "user", userId, payload);
  if (!principal) {
    return {
      user_id: userId,
      role_ids: [],
      role_slugs: [],
      created_at: new Date().toISOString(),
    };
  }
  return {
    user_id: principal.principal_id,
    role_ids: principal.role_ids,
    role_slugs: principal.role_slugs,
    created_at: principal.created_at,
    user: principal.principal_email
      ? ({
          id: principal.principal_id,
          email: principal.principal_email,
          display_name: principal.principal_display_name ?? null,
        } as WorkspaceMember["user"])
      : undefined,
  };
}

export async function removeWorkspaceMember(workspaceId: string, userId: string) {
  await removeWorkspacePrincipal(workspaceId, "user", userId);
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
    params: {
      path: { roleId },
      header: { "If-Match": options.ifMatch ?? "*" },
    },
    body: payload,
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
    params: {
      path: { roleId },
      header: { "If-Match": options.ifMatch ?? "*" },
    },
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
