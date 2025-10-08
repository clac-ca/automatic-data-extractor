import { useQuery } from "@tanstack/react-query";

import { fetchSession } from "../api";
import { sessionKeys } from "./sessionKeys";
import type { SessionEnvelope } from "../../../shared/api/types";

export function useOptionalSession() {
  return useQuery<SessionEnvelope | null>({
    queryKey: sessionKeys.detail(),
    queryFn: fetchSession,
    staleTime: 30_000,
  });
}
