import { buildListQuery, type FilterItem } from "@/api/listing";
import { client } from "@/api/client";
import type { components } from "@/types";

export type AdminRole = components["schemas"]["RoleOut"];
export type AdminRolePage = components["schemas"]["RolePage"];
export type AdminRoleCreateRequest = components["schemas"]["RoleCreate"];
export type AdminRoleUpdateRequest = components["schemas"]["RoleUpdate"];
export type AdminPermissionPage = components["schemas"]["PermissionPage"];
export type AdminPermission = components["schemas"]["PermissionOut"];
type RoleAssignmentOut = components["schemas"]["RoleAssignmentOut"];
export interface AdminUserRoles {
  readonly user_id: string;
  readonly roles: ReadonlyArray<{
    readonly role_id: string;
    readonly role_slug: string;
    readonly created_at: string;
  }>;
}

async function listOrganizationRoleAssignments(signal?: AbortSignal): Promise<RoleAssignmentOut[]> {
  const { data } = await client.GET("/api/v1/roleAssignments", { signal });
  if (!data?.items) {
    throw new Error("Expected role assignments payload.");
  }
  return data.items as RoleAssignmentOut[];
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
  const assignments = (await listOrganizationRoleAssignments(options.signal)).filter(
    (assignment) =>
      assignment.principal_type === "user" &&
      assignment.principal_id === userId &&
      assignment.scope_type === "organization",
  );

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
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  const assignments = await listOrganizationRoleAssignments();
  const assignment = assignments.find(
    (entry) =>
      entry.principal_type === "user" &&
      entry.principal_id === userId &&
      entry.role_id === roleId &&
      entry.scope_type === "organization",
  );
  if (!assignment) return;
  await client.DELETE("/api/v1/roleAssignments/{assignmentId}", {
    params: {
      path: { assignmentId: assignment.id },
      header: { "If-Match": options.ifMatch ?? "*" },
    },
  });
}
