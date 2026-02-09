import { client } from "@/api/client";
import type { components } from "@/types";

export type AdminSettingsReadResponse = components["schemas"]["AdminSettingsReadResponse"];
export type AdminSettingsPatchRequest = components["schemas"]["AdminSettingsPatchRequest"];

export async function readAdminSettings(
  options: { signal?: AbortSignal } = {},
): Promise<AdminSettingsReadResponse> {
  const { data } = await client.GET("/api/v1/admin/settings", {
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected admin settings payload.");
  }

  return data;
}

export async function patchAdminSettings(
  payload: AdminSettingsPatchRequest,
): Promise<AdminSettingsReadResponse> {
  const { data } = await client.PATCH("/api/v1/admin/settings", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected updated admin settings payload.");
  }

  return data;
}
