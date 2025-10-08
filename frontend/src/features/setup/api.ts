import { get, post } from "../../shared/api/client";
import type { CompleteSetupPayload, SetupStatusResponse, SessionEnvelope } from "../../shared/api/types";

export async function fetchSetupStatus() {
  return get<SetupStatusResponse>("/setup/status");
}

export async function completeSetup(payload: CompleteSetupPayload) {
  return post<SessionEnvelope>("/setup", payload);
}
