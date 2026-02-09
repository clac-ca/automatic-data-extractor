import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchSystemVersions, type SystemVersions } from "@/api/system/api";

const SYSTEM_VERSIONS_QUERY_KEY = ["system", "versions"] as const;

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

export type { SystemVersions };
