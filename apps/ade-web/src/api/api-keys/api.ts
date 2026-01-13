import { client } from "@api/client";
import { createIdempotencyKey } from "@api/idempotency";
import { buildListQuery, type FilterItem } from "@api/listing";
import type { ApiKeyCreateResponse, ApiKeyPage, components } from "@schema";

export interface ListPageOptions {
  readonly limit?: number;
  readonly cursor?: string | null;
  readonly includeRevoked?: boolean;
  readonly sort?: string;
  readonly q?: string;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

type CreateApiKeyRequest = components["schemas"]["ApiKeyCreateRequest"];

export async function listMyApiKeys(options: ListPageOptions = {}): Promise<ApiKeyPage> {
  const query = buildApiKeyListQuery(options);
  const { data } = await client.GET("/api/v1/users/me/apikeys", {
    params: { query },
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected API key page payload.");
  }
  return data;
}

export async function createMyApiKey(
  payload: CreateApiKeyRequest,
  idempotencyKey?: string,
): Promise<ApiKeyCreateResponse> {
  const { data } = await client.POST("/api/v1/users/me/apikeys", {
    body: payload,
    headers: {
      "Idempotency-Key": idempotencyKey ?? createIdempotencyKey("api-key"),
    },
  });
  if (!data) {
    throw new Error("Expected API key creation payload.");
  }
  return data;
}

export async function revokeMyApiKey(apiKeyId: string, options: { ifMatch?: string | null } = {}): Promise<void> {
  await client.DELETE("/api/v1/users/me/apikeys/{apiKeyId}", {
    params: { path: { apiKeyId: apiKeyId } },
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });
}

export async function listUserApiKeys(userId: string, options: ListPageOptions = {}): Promise<ApiKeyPage> {
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

export async function createUserApiKey(
  userId: string,
  payload: CreateApiKeyRequest,
  idempotencyKey?: string,
): Promise<ApiKeyCreateResponse> {
  const { data } = await client.POST("/api/v1/users/{userId}/apikeys", {
    params: { path: { userId } },
    body: payload,
    headers: {
      "Idempotency-Key": idempotencyKey ?? createIdempotencyKey("api-key"),
    },
  });
  if (!data) {
    throw new Error("Expected API key creation payload.");
  }
  return data;
}

export async function revokeUserApiKey(
  userId: string,
  apiKeyId: string,
  options: { ifMatch?: string | null } = {},
): Promise<void> {
  await client.DELETE("/api/v1/users/{userId}/apikeys/{apiKeyId}", {
    params: { path: { userId, apiKeyId } },
    headers: options.ifMatch ? { "If-Match": options.ifMatch } : undefined,
  });
}

function buildApiKeyListQuery(options: ListPageOptions) {
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
