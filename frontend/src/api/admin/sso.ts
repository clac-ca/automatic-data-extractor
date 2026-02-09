import { client } from "@/api/client";
import type { components } from "@/types";

export type SsoProviderAdmin = components["schemas"]["SsoProviderAdminOut"];
export type SsoProviderListResponse = components["schemas"]["SsoProviderListResponse"];
export type SsoProviderCreateRequest = components["schemas"]["SsoProviderCreate"];
export type SsoProviderUpdateRequest = components["schemas"]["SsoProviderUpdate"];
export type SsoProviderValidateRequest = components["schemas"]["SsoProviderValidateRequest"];
export type SsoProviderValidationResponse = components["schemas"]["SsoProviderValidationResponse"];

export async function listSsoProviders(options: { signal?: AbortSignal } = {}): Promise<SsoProviderListResponse> {
  const { data } = await client.GET("/api/v1/admin/sso/providers", {
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected SSO provider list payload.");
  }

  return data;
}

export async function createSsoProvider(payload: SsoProviderCreateRequest): Promise<SsoProviderAdmin> {
  const { data } = await client.POST("/api/v1/admin/sso/providers", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected SSO provider payload.");
  }

  return data;
}

export async function validateSsoProvider(
  payload: SsoProviderValidateRequest,
): Promise<SsoProviderValidationResponse> {
  const { data } = await client.POST("/api/v1/admin/sso/providers/validate", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected SSO provider validation payload.");
  }

  return data;
}

export async function updateSsoProvider(id: string, payload: SsoProviderUpdateRequest): Promise<SsoProviderAdmin> {
  const { data } = await client.PATCH("/api/v1/admin/sso/providers/{id}", {
    params: { path: { id } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected SSO provider payload.");
  }

  return data;
}

export async function deleteSsoProvider(id: string): Promise<void> {
  await client.DELETE("/api/v1/admin/sso/providers/{id}", {
    params: { path: { id } },
  });
}
