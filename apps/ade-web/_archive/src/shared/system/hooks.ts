import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  DEFAULT_SAFE_MODE_MESSAGE,
  fetchSafeModeStatus,
  updateSafeModeStatus,
  type SafeModeStatus,
  type SafeModeUpdateRequest,
} from "./api";

const SAFE_MODE_QUERY_KEY = ["system", "safe-mode"] as const;

export function useSafeModeStatus() {
  return useQuery<SafeModeStatus>({
    queryKey: SAFE_MODE_QUERY_KEY,
    queryFn: ({ signal }) => fetchSafeModeStatus({ signal }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useUpdateSafeModeStatus() {
  const queryClient = useQueryClient();
  return useMutation<SafeModeStatus, Error, SafeModeUpdateRequest>({
    mutationFn: (payload) => updateSafeModeStatus(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SAFE_MODE_QUERY_KEY });
    },
  });
}

export { DEFAULT_SAFE_MODE_MESSAGE, type SafeModeStatus, type SafeModeUpdateRequest };
