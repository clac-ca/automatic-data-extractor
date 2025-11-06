import { useQuery } from "@tanstack/react-query";

import { DEFAULT_SAFE_MODE_MESSAGE, fetchSafeModeStatus, type SafeModeStatus } from "./api";

const SAFE_MODE_QUERY_KEY = ["system", "safe-mode"] as const;

export function useSafeModeStatus() {
  return useQuery<SafeModeStatus>({
    queryKey: SAFE_MODE_QUERY_KEY,
    queryFn: ({ signal }) => fetchSafeModeStatus({ signal }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export { DEFAULT_SAFE_MODE_MESSAGE, type SafeModeStatus };
