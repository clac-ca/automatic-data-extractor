import { client } from "@/api/client";
import { buildListQuery } from "@/api/listing";
import type { components } from "@/types";

export type AdminUser = components["schemas"]["UserOut"];
export type AdminUserPage = components["schemas"]["UserPage"];
export type AdminUserCreateRequest = components["schemas"]["UserCreate"];
export type AdminUserCreateResponse = components["schemas"]["UserCreateResponse"];
export type AdminUserUpdateRequest = components["schemas"]["UserUpdate"];

export interface ListAdminUsersOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly search?: string;
  readonly sort?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listAdminUsers(options: ListAdminUsersOptions = {}): Promise<AdminUserPage> {
  const query = buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.search?.trim() || null,
    includeTotal: options.includeTotal,
  });

  const { data } = await client.GET("/api/v1/users", {
    params: { query },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected user page payload.");
  }

  return data;
}

export async function createAdminUser(
  payload: AdminUserCreateRequest,
): Promise<AdminUserCreateResponse> {
  const { data } = await client.POST("/api/v1/users", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected create-user payload.");
  }

  return data;
}

export async function getAdminUser(userId: string, options: { signal?: AbortSignal } = {}): Promise<AdminUser> {
  const { data } = await client.GET("/api/v1/users/{userId}", {
    params: { path: { userId } },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected user payload.");
  }

  return data;
}

export async function updateAdminUser(userId: string, payload: AdminUserUpdateRequest): Promise<AdminUser> {
  const { data } = await client.PATCH("/api/v1/users/{userId}", {
    params: { path: { userId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected user payload.");
  }

  return data;
}

export async function deactivateAdminUser(userId: string): Promise<AdminUser> {
  const { data } = await client.POST("/api/v1/users/{userId}/deactivate", {
    params: { path: { userId } },
  });

  if (!data) {
    throw new Error("Expected user payload.");
  }

  return data;
}
