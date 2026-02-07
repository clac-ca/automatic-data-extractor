import { buildListQuery, type FilterItem } from "@/api/listing";
import { client } from "@/api/client";
import type { ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyPage } from "@/types";

export interface AdminApiKeyListOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly includeRevoked?: boolean;
  readonly sort?: string | null;
  readonly q?: string | null;
  readonly includeTotal?: boolean;
  readonly userId?: string | null;
  readonly signal?: AbortSignal;
}

function buildApiKeyListQuery(options: AdminApiKeyListOptions) {
  const filters: FilterItem[] = [];
  if (!options.includeRevoked) {
    filters.push({ id: "revokedAt", operator: "isEmpty" });
  }

  return buildListQuery({
    limit: options.limit,
    cursor: options.cursor ?? null,
    sort: options.sort ?? null,
    q: options.q ?? null,
    filters,
    includeTotal: options.includeTotal,
  });
}

export async function listTenantApiKeys(options: AdminApiKeyListOptions = {}): Promise<ApiKeyPage> {
  const query = buildApiKeyListQuery(options);
  const paramsQuery = options.userId ? { ...query, userId: options.userId } : query;

  const { data } = await client.GET("/api/v1/apikeys", {
    params: { query: paramsQuery },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected API key page payload.");
  }

  return data;
}

export async function listAdminUserApiKeys(userId: string, options: AdminApiKeyListOptions = {}): Promise<ApiKeyPage> {
  const query = buildApiKeyListQuery(options);
  const { data } = await client.GET("/api/v1/users/{userId}/apikeys", {
    params: { path: { userId }, query },
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected API key page payload.");
  }

  return data;
}

export async function createAdminUserApiKey(
  userId: string,
  payload: ApiKeyCreateRequest,
): Promise<ApiKeyCreateResponse> {
  const { data } = await client.POST("/api/v1/users/{userId}/apikeys", {
    params: { path: { userId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected API key creation payload.");
  }

  return data;
}

export async function revokeAdminUserApiKey(
  userId: string,
  apiKeyId: string,
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/users/{userId}/apikeys/{apiKeyId}", {
    params: {
      path: { userId, apiKeyId },
      header: { "If-Match": options.ifMatch ?? "*" },
    },
  });
}
