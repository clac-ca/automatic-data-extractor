import { client } from "@shared/api/client";

export interface SafeModeStatus {
  readonly enabled: boolean;
  readonly detail: string;
}

export interface SafeModeUpdateRequest {
  readonly enabled: boolean;
  readonly detail?: string | null;
}

interface RequestOptions {
  readonly signal?: AbortSignal;
}

export async function fetchSafeModeStatus(options: RequestOptions = {}): Promise<SafeModeStatus> {
  const { data } = await client.GET("/api/v1/system/safe-mode", {
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

export async function updateSafeModeStatus(
  payload: SafeModeUpdateRequest,
  options: RequestOptions = {},
): Promise<SafeModeStatus> {
  await client.PUT("/api/v1/system/safe-mode", {
    body: payload,
    signal: options.signal,
  });

  return fetchSafeModeStatus(options);
}

export const DEFAULT_SAFE_MODE_MESSAGE =
  "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled.";
