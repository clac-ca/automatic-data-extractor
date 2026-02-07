import { client } from "@/api/client";
import type { components } from "@/types";

export type SsoProviderAdmin = components["schemas"]["SsoProviderAdminOut"];
export type SsoProviderListResponse = components["schemas"]["SsoProviderListResponse"];
export type SsoProviderCreateRequest = components["schemas"]["SsoProviderCreate"];
export type SsoProviderUpdateRequest = components["schemas"]["SsoProviderUpdate"];
export type SsoSettings = components["schemas"]["SsoSettings"];
export type SafeModeStatus = components["schemas"]["SafeModeStatus"];
export type SafeModeUpdateRequest = components["schemas"]["SafeModeUpdateRequest"];

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

export async function readSsoSettings(options: { signal?: AbortSignal } = {}): Promise<SsoSettings> {
  const { data } = await client.GET("/api/v1/admin/sso/settings", {
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected SSO settings payload.");
  }

  return data;
}

export async function updateSsoSettings(payload: SsoSettings): Promise<SsoSettings> {
  const { data } = await client.PUT("/api/v1/admin/sso/settings", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected SSO settings payload.");
  }

  return data;
}

export async function readSafeModeStatus(options: { signal?: AbortSignal } = {}): Promise<SafeModeStatus> {
  const { data } = await client.GET("/api/v1/system/safemode", {
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected safe mode payload.");
  }

  return data;
}

export async function updateSafeModeStatus(payload: SafeModeUpdateRequest): Promise<SafeModeStatus> {
  await client.PUT("/api/v1/system/safemode", {
    body: payload,
  });
  return readSafeModeStatus();
}
