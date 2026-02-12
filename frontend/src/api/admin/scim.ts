import { client } from "@/api/client";
import type { components } from "@/types";

export type ScimTokenOut = components["schemas"]["ScimTokenOut"];
export type ScimTokenListResponse = components["schemas"]["ScimTokenListResponse"];
export type ScimTokenCreateRequest = components["schemas"]["ScimTokenCreateRequest"];
export type ScimTokenCreateResponse = components["schemas"]["ScimTokenCreateResponse"];

export async function listScimTokens(
  options: { signal?: AbortSignal } = {},
): Promise<ScimTokenListResponse> {
  const { data } = await client.GET("/api/v1/admin/scim/tokens", {
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected SCIM token list payload.");
  }
  return data;
}

export async function createScimToken(
  payload: ScimTokenCreateRequest,
): Promise<ScimTokenCreateResponse> {
  const { data } = await client.POST("/api/v1/admin/scim/tokens", {
    body: payload,
  });
  if (!data) {
    throw new Error("Expected SCIM token payload.");
  }
  return data;
}

export async function revokeScimToken(tokenId: string): Promise<ScimTokenOut> {
  const { data } = await client.POST("/api/v1/admin/scim/tokens/{tokenId}/revoke", {
    params: { path: { tokenId } },
  });
  if (!data) {
    throw new Error("Expected revoked SCIM token payload.");
  }
  return data;
}
