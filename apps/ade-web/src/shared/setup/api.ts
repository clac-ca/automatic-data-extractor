import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import { establishSessionFromTokens, type SessionEnvelope } from "@shared/auth/api";
import type { AuthSetupRequest, AuthSetupStatus, components } from "@schema";

export async function fetchSetupStatus(options: RequestOptions = {}): Promise<AuthSetupStatus> {
  try {
    const { data } = await client.GET("/api/v1/auth/setup", {
      signal: options.signal,
    });
    if (!data) {
      throw new Error("Expected setup status payload.");
    }
    return data;
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { requires_setup: false, has_users: true };
    }
    throw error;
  }
}

export async function completeSetup(payload: SetupPayload): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/setup", {
    body: payload as AuthSetupRequest,
  });

  if (!data) {
    throw new Error("Expected tokens from setup response.");
  }

  return establishSessionFromTokens(data);
}

type SetupPayload = components["schemas"]["AuthSetupRequest"];
export type SetupStatus = AuthSetupStatus;

interface RequestOptions {
  readonly signal?: AbortSignal;
}
