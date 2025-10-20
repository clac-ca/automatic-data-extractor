import { client } from "@shared/api/client";
import type { SessionEnvelope, SetupPayload, SetupStatus } from "@schema/auth";

export async function fetchSetupStatus() {
  const { data } = await client.GET("/api/v1/setup/status");
  if (!data) {
    throw new Error("Expected setup status payload.");
  }
  return data as SetupStatus;
}

export async function completeSetup(payload: SetupPayload) {
  const { data } = await client.POST("/api/v1/setup", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected session payload.");
  }

  return data as SessionEnvelope;
}
