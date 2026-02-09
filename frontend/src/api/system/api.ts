import { client } from "@/api/client";
import type { components } from "@/types";

export type SystemVersions = components["schemas"]["VersionsResponse"];

interface RequestOptions {
  readonly signal?: AbortSignal;
}

export async function fetchSystemVersions(options: RequestOptions = {}): Promise<SystemVersions> {
  const { data } = await client.GET("/api/v1/meta/versions", {
    signal: options.signal,
  });

  const payload = (data ?? {}) as Partial<SystemVersions>;
  return {
    backend: normalizeVersion(payload.backend),
    engine: normalizeVersion(payload.engine),
    web: normalizeVersion(payload.web),
  };
}

function normalizeVersion(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : "unknown";
}
