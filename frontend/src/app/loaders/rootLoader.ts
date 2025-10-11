import { appQueryClient } from "../providers";
import { fetchSession } from "../../features/auth/api";
import { sessionKeys } from "../../features/auth/hooks/sessionKeys";
import { fetchSetupStatus } from "../../features/setup/api";
import { setupKeys } from "../../features/setup/hooks/useSetupStatusQuery";
import type { SessionEnvelope, SetupStatusResponse } from "../../shared/api/types";

export interface RootLoaderData {
  session: SessionEnvelope | null;
  setupStatus: SetupStatusResponse | null;
  setupError: unknown | null;
}

export async function rootLoader(): Promise<RootLoaderData> {
  const [sessionResult, setupResult] = await Promise.allSettled([
    appQueryClient.ensureQueryData({
      queryKey: sessionKeys.detail(),
      queryFn: fetchSession,
    }),
    appQueryClient.ensureQueryData({
      queryKey: setupKeys.status(),
      queryFn: fetchSetupStatus,
    }),
  ]);

  if (sessionResult.status === "rejected") {
    throw sessionResult.reason;
  }

  if (setupResult.status === "rejected") {
    return {
      session: sessionResult.value,
      setupStatus: null,
      setupError: setupResult.reason,
    };
  }

  return {
    session: sessionResult.value,
    setupStatus: setupResult.value,
    setupError: null,
  };
}
