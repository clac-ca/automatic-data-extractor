import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import { normalizeSessionEnvelope, type SessionEnvelope } from "@shared/auth/api";
import type { components } from "@openapi";

export async function fetchSetupStatus(options: RequestOptions = {}): Promise<SetupStatus> {
  try {
    const { data } = await client.GET("/api/v1/setup/status", {
      signal: options.signal,
    });
    if (!data) {
      throw new Error("Expected setup status payload.");
    }
    return data as SetupStatus;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { requires_setup: false, force_sso: false };
    }
    throw error;
  }
}

export async function completeSetup(payload: SetupPayload): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/setup", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected session payload.");
  }

  return normalizeSessionEnvelope(data);
}

export type SetupStatus = components["schemas"]["SetupStatus"];
export type SetupPayload = components["schemas"]["SetupRequest"];

interface RequestOptions {
  readonly signal?: AbortSignal;
}
