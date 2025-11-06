import { client } from "@shared/api/client";
import type { components } from "@openapi";

export interface SafeModeStatus {
  readonly enabled: boolean;
  readonly detail: string;
}

interface RequestOptions {
  readonly signal?: AbortSignal;
}

export async function fetchSafeModeStatus(options: RequestOptions = {}): Promise<SafeModeStatus> {
  const { data } = await client.GET("/api/v1/health", {
    signal: options.signal,
  });

  const payload = (data ?? {}) as Partial<HealthCheckResponse>;
  const components = Array.isArray(payload.components) ? payload.components : [];
  const safeModeComponent = components.find((component) => component?.name === "safe-mode");

  const enabled = safeModeComponent?.status === "degraded";
  const detail =
    (typeof safeModeComponent?.detail === "string" && safeModeComponent.detail.trim().length > 0
      ? safeModeComponent.detail.trim()
      : DEFAULT_SAFE_MODE_MESSAGE);

  return { enabled, detail };
}

export const DEFAULT_SAFE_MODE_MESSAGE =
  "ADE_SAFE_MODE is enabled. Job execution is temporarily disabled so you can revert config changes and restart without safe mode.";

type HealthCheckResponse = components["schemas"]["HealthCheckResponse"];
