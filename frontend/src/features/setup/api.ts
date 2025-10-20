import { get, post } from "@shared/api";
import type { SessionEnvelope, SetupPayload, SetupStatus } from "@types/auth";

export async function fetchSetupStatus() {
  return get<SetupStatus>("/setup/status");
}

export async function completeSetup(payload: SetupPayload) {
  return post<SessionEnvelope>("/setup", payload);
}
