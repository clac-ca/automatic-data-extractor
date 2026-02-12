import { buildListQuery, type FilterItem } from "@/api/listing";
import { collectAllPages, MAX_PAGE_SIZE } from "@/api/pagination";
import { client } from "@/api/client";
import type { components } from "@/types";

export type AdminRole = components["schemas"]["RoleOut"];
export type AdminRolePage = components["schemas"]["RolePage"];
export type AdminRoleCreateRequest = components["schemas"]["RoleCreate"];
export type AdminRoleUpdateRequest = components["schemas"]["RoleUpdate"];
export type AdminPermissionPage = components["schemas"]["PermissionPage"];
export type AdminPermission = components["schemas"]["PermissionOut"];
type RoleAssignmentOut = components["schemas"]["RoleAssignmentOut"];
type RoleAssignmentPage = components["schemas"]["RoleAssignmentPage"];
export interface AdminUserRoles {
  readonly user_id: string;
  readonly roles: ReadonlyArray<{
    readonly role_id: string;
    readonly role_slug: string;
    readonly created_at: string;
  }>;
}

const ROLE_ASSIGNMENT_PAGE_SIZE = MAX_PAGE_SIZE;

interface ListOrganizationRoleAssignmentsOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly sort?: string | null;
  readonly q?: string | null;
  readonly filters?: FilterItem[];
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

async function listOrganizationRoleAssignmentsPage(
  options: ListOrganizationRoleAssignmentsOptions = {},
): Promise<RoleAssignmentPage> {
  const query = buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.q ?? null,
    filters: options.filters,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/roleAssignments", {
    params: { query },
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected role assignments payload.");
  }
  return data;
}

async function listOrganizationRoleAssignments(
  options: Omit<ListOrganizationRoleAssignmentsOptions, "cursor"> = {},
): Promise<RoleAssignmentOut[]> {
  const page = await collectAllPages((cursor) =>
    listOrganizationRoleAssignmentsPage({
      ...options,
      cursor,
      limit: options.limit ?? ROLE_ASSIGNMENT_PAGE_SIZE,
      includeTotal: true,
    }),
  );
  return page.items as RoleAssignmentOut[];
}

export interface ListAdminRolesOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly q?: string | null;
  readonly sort?: string | null;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listAdminRoles(options: ListAdminRolesOptions = {}): Promise<AdminRolePage> {
  const filters: FilterItem[] = [{ id: "scopeType", operator: "eq", value: "global" }];
  const query = buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.q ?? null,
    filters,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/roles", {
    params: { query },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected role page payload.");
  }

  return data;
}

export async function createAdminRole(payload: AdminRoleCreateRequest): Promise<AdminRole> {
  const { data } = await client.POST("/api/v1/roles", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function updateAdminRole(
  roleId: string,
  payload: AdminRoleUpdateRequest,
  options: { ifMatch?: string | null } = {},
): Promise<AdminRole> {
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

export async function deleteAdminRole(roleId: string, options: { ifMatch?: string | null } = {}): Promise<void> {
  await client.DELETE("/api/v1/roles/{roleId}", {
    params: {
      path: { roleId },
      header: { "If-Match": options.ifMatch ?? "*" },
    },
  });
}

export interface ListAdminPermissionsOptions {
  readonly scope?: "global" | "workspace";
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly q?: string | null;
  readonly sort?: string | null;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listAdminPermissions(
  options: ListAdminPermissionsOptions = {},
): Promise<AdminPermissionPage> {
  const scope = options.scope ?? "global";
  const filters: FilterItem[] = [{ id: "scopeType", operator: "eq", value: scope }];
  const query = buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.q ?? null,
    filters,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/permissions", {
    params: { query },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected permission page payload.");
  }

  return data;
}

export async function listAdminUserRoles(userId: string, options: { signal?: AbortSignal } = {}): Promise<AdminUserRoles> {
  const assignments = await listOrganizationRoleAssignments({
    signal: options.signal,
    filters: [
      { id: "principalType", operator: "eq", value: "user" },
      { id: "principalId", operator: "eq", value: userId },
      { id: "scopeType", operator: "eq", value: "organization" },
    ],
  });

  return {
    user_id: userId,
    roles: assignments.map((assignment) => ({
      role_id: assignment.role_id,
      role_slug: assignment.role_slug,
      created_at: assignment.created_at,
    })),
  };
}

export async function assignAdminUserRole(userId: string, roleId: string): Promise<AdminUserRoles> {
  await client.POST("/api/v1/roleAssignments", {
    body: {
      principal_type: "user",
      principal_id: userId,
      role_id: roleId,
    },
  });
  return listAdminUserRoles(userId);
}

export async function removeAdminUserRole(
  userId: string,
  roleId: string,
  options: { signal?: AbortSignal } = {},
): Promise<void> {
  const matching = await listOrganizationRoleAssignmentsPage({
    limit: 1,
    includeTotal: false,
    signal: options.signal,
    filters: [
      { id: "principalType", operator: "eq", value: "user" },
      { id: "principalId", operator: "eq", value: userId },
      { id: "roleId", operator: "eq", value: roleId },
      { id: "scopeType", operator: "eq", value: "organization" },
    ],
  });
  const assignment = matching.items[0];
  if (!assignment) return;
  await client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
    params: {
      path: { assignmentId: assignment.id },
    },
  });
}
