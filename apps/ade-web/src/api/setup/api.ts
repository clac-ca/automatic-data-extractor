import { ApiError } from "@/api/errors";
import { client } from "@/api/client";
import { bootstrapSession, type SessionEnvelope } from "@/api/auth/api";
import type { AuthSetupRequest, AuthSetupStatus, components } from "@/types";

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
      return {
        setup_required: false,
        registration_mode: "closed",
        oidc_configured: false,
        providers: [],
      };
    }
    throw error;
  }
}

export async function completeSetup(payload: SetupPayload): Promise<SessionEnvelope> {
  await client.POST("/api/v1/auth/setup", {
    body: payload as AuthSetupRequest,
  });
  return bootstrapSession();
}

type SetupPayload = components["schemas"]["AuthSetupRequest"];
export type SetupStatus = AuthSetupStatus;

interface RequestOptions {
  readonly signal?: AbortSignal;
}
