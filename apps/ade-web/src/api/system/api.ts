import { client } from "@api/client";
import type { components } from "@schema";

export type SafeModeStatus = components["schemas"]["SafeModeStatus"];
export type SafeModeUpdateRequest = components["schemas"]["SafeModeUpdateRequest"];
export type SystemVersions = components["schemas"]["VersionsResponse"];

interface RequestOptions {
  readonly signal?: AbortSignal;
}

export async function fetchSafeModeStatus(options: RequestOptions = {}): Promise<SafeModeStatus> {
  const { data } = await client.GET("/api/v1/system/safemode", {
    signal: options.signal,
  });

  const payload = (data ?? {}) as Partial<SafeModeStatus>;
  const enabled = Boolean(payload.enabled);
  const detail =
    typeof payload.detail === "string" && payload.detail.trim().length > 0
      ? payload.detail.trim()
      : DEFAULT_SAFE_MODE_MESSAGE;

  return { enabled, detail };
}

export async function fetchSystemVersions(options: RequestOptions = {}): Promise<SystemVersions> {
  const { data } = await client.GET("/api/v1/meta/versions", {
    signal: options.signal,
  });

  const payload = (data ?? {}) as Partial<SystemVersions>;
  return {
    ade_api: normalizeVersion(payload.ade_api),
    ade_engine: normalizeVersion(payload.ade_engine),
  };
}

export async function updateSafeModeStatus(
  payload: SafeModeUpdateRequest,
  options: RequestOptions = {},
): Promise<SafeModeStatus> {
  await client.PUT("/api/v1/system/safemode", {
    body: payload,
    signal: options.signal,
  });

  return fetchSafeModeStatus(options);
}

export const DEFAULT_SAFE_MODE_MESSAGE =
  "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled.";

function normalizeVersion(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : "unknown";
}
