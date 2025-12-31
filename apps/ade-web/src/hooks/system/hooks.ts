import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  DEFAULT_SAFE_MODE_MESSAGE,
  fetchSafeModeStatus,
  fetchSystemVersions,
  updateSafeModeStatus,
  type SafeModeStatus,
  type SafeModeUpdateRequest,
  type SystemVersions,
} from "@api/system/api";

export const SAFE_MODE_QUERY_KEY = ["system", "safeMode"] as const;
export const SYSTEM_VERSIONS_QUERY_KEY = ["system", "versions"] as const;

export function useSafeModeStatus() {
  const queryClient = useQueryClient();
  const initialData = queryClient.getQueryData<SafeModeStatus>(SAFE_MODE_QUERY_KEY);
  return useQuery<SafeModeStatus>({
    queryKey: SAFE_MODE_QUERY_KEY,
    queryFn: ({ signal }) => fetchSafeModeStatus({ signal }),
    initialData,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useUpdateSafeModeStatus() {
  const queryClient = useQueryClient();
  return useMutation<SafeModeStatus, Error, SafeModeUpdateRequest>({
    mutationFn: (payload) => updateSafeModeStatus(payload),
    onSuccess: (nextStatus) => {
      queryClient.setQueryData(SAFE_MODE_QUERY_KEY, nextStatus);
    },
  });
}

export function useSystemVersions(options: { enabled?: boolean } = {}) {
  const queryClient = useQueryClient();
  const initialData = queryClient.getQueryData<SystemVersions>(SYSTEM_VERSIONS_QUERY_KEY);

  return useQuery<SystemVersions>({
    queryKey: SYSTEM_VERSIONS_QUERY_KEY,
    queryFn: ({ signal }) => fetchSystemVersions({ signal }),
    initialData,
    staleTime: 5 * 60 * 1000,
    enabled: options.enabled ?? true,
  });
}

export {
  DEFAULT_SAFE_MODE_MESSAGE,
  type SafeModeStatus,
  type SafeModeUpdateRequest,
  type SystemVersions,
};
