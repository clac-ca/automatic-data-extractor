import { client } from "@shared/api/client";
import type { ApiKeyCreateResponse, ApiKeyPage, components, paths } from "@schema";

export interface ListPageOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly includeRevoked?: boolean;
  readonly signal?: AbortSignal;
}

type ListMyApiKeysQuery = NonNullable<paths["/api/v1/users/me/api-keys"]["get"]["parameters"]["query"]>;
type ListUserApiKeysQuery = NonNullable<
  paths["/api/v1/users/{user_id}/api-keys"]["get"]["parameters"]["query"]
>;
type ListQuery = ListMyApiKeysQuery;

type CreateApiKeyRequest = components["schemas"]["ApiKeyCreateRequest"];

export async function listMyApiKeys(options: ListPageOptions = {}): Promise<ApiKeyPage> {
  const query = buildListQuery(options);
  const { data } = await client.GET("/api/v1/users/me/api-keys", {
    params: { query },
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected API key page payload.");
  }
  return data;
}

export async function createMyApiKey(payload: CreateApiKeyRequest): Promise<ApiKeyCreateResponse> {
  const { data } = await client.POST("/api/v1/users/me/api-keys", { body: payload });
  if (!data) {
    throw new Error("Expected API key creation payload.");
  }
  return data;
}

export async function revokeMyApiKey(apiKeyId: string): Promise<void> {
  await client.DELETE("/api/v1/users/me/api-keys/{api_key_id}", {
    params: { path: { api_key_id: apiKeyId } },
  });
}

export async function listUserApiKeys(userId: string, options: ListPageOptions = {}): Promise<ApiKeyPage> {
  const query: ListUserApiKeysQuery = buildListQuery(options);
  const { data } = await client.GET("/api/v1/users/{user_id}/api-keys", {
    params: { path: { user_id: userId }, query },
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
  const { data } = await client.POST("/api/v1/users/{user_id}/api-keys", {
    params: { path: { user_id: userId } },
    body: payload,
  });
  if (!data) {
    throw new Error("Expected API key creation payload.");
  }
  return data;
}

export async function revokeUserApiKey(userId: string, apiKeyId: string): Promise<void> {
  await client.DELETE("/api/v1/users/{user_id}/api-keys/{api_key_id}", {
    params: { path: { user_id: userId, api_key_id: apiKeyId } },
  });
}

function buildListQuery(options: ListPageOptions): ListQuery {
  const query: ListQuery = {};
  if (typeof options.page === "number" && options.page > 0) {
    query.page = options.page;
  }
  if (typeof options.pageSize === "number" && options.pageSize > 0) {
    query.page_size = options.pageSize;
  }
  if (options.includeTotal) {
    query.include_total = true;
  }
  if (options.includeRevoked) {
    query.include_revoked = true;
  }
  return query;
}
