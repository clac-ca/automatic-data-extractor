import { buildListQuery, type FilterItem } from "@/api/listing";
import { client } from "@/api/client";
import type { components } from "@/types";

export type AdminRole = components["schemas"]["RoleOut"];
export type AdminRolePage = components["schemas"]["RolePage"];
export type AdminRoleCreateRequest = components["schemas"]["RoleCreate"];
export type AdminRoleUpdateRequest = components["schemas"]["RoleUpdate"];
export type AdminPermissionPage = components["schemas"]["PermissionPage"];
export type AdminPermission = components["schemas"]["PermissionOut"];
export type AdminUserRoles = components["schemas"]["UserRolesEnvelope"];

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
  const rolePayload: AdminRoleCreateRequest = {
    ...payload,
    scope_type: "global",
  };
  const { data } = await client.POST("/api/v1/roles", {
    body: rolePayload,
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
    params: { path: { roleId } },
    body: payload,
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function deleteAdminRole(roleId: string, options: { ifMatch?: string | null } = {}): Promise<void> {
  await client.DELETE("/api/v1/roles/{roleId}", {
    params: { path: { roleId } },
    headers: { "If-Match": options.ifMatch ?? "*" },
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
  const { data } = await client.GET("/api/v1/users/{userId}/roles", {
    params: { path: { userId } },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected user roles payload.");
  }

  return data;
}

export async function assignAdminUserRole(userId: string, roleId: string): Promise<AdminUserRoles> {
  const { data } = await client.PUT("/api/v1/users/{userId}/roles/{roleId}", {
    params: { path: { userId, roleId } },
  });

  if (!data) {
    throw new Error("Expected user roles payload.");
  }

  return data;
}

export async function removeAdminUserRole(
  userId: string,
  roleId: string,
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/users/{userId}/roles/{roleId}", {
    params: { path: { userId, roleId } },
    headers: { "If-Match": options.ifMatch ?? "*" },
  });
}
