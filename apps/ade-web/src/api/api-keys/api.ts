import { client } from "@api/client";
import { buildListQuery, type FilterItem } from "@api/listing";
import type { ApiKeyCreateResponse, ApiKeyPage, components } from "@schema";

export interface ListPageOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeRevoked?: boolean;
  readonly sort?: string;
  readonly q?: string;
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

export async function createMyApiKey(payload: CreateApiKeyRequest): Promise<ApiKeyCreateResponse> {
  const { data } = await client.POST("/api/v1/users/me/apikeys", { body: payload });
  if (!data) {
    throw new Error("Expected API key creation payload.");
  }
  return data;
}

export async function revokeMyApiKey(apiKeyId: string): Promise<void> {
  await client.DELETE("/api/v1/users/me/apikeys/{apiKeyId}", {
    params: { path: { apiKeyId: apiKeyId } },
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

export async function revokeUserApiKey(userId: string, apiKeyId: string): Promise<void> {
  await client.DELETE("/api/v1/users/{userId}/apikeys/{apiKeyId}", {
    params: { path: { userId, apiKeyId } },
  });
}

function buildApiKeyListQuery(options: ListPageOptions) {
  const filters: FilterItem[] = [];
  if (!options.includeRevoked) {
    filters.push({ id: "revokedAt", operator: "isEmpty" });
  }
  return buildListQuery({
    page: options.page,
    perPage: options.pageSize,
    sort: options.sort ?? null,
    q: options.q ?? null,
    filters,
  });
}
