import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaces } from "@api/workspaces/api";
import { WORKSPACE_LIST_DEFAULT_PARAMS, workspacesKeys } from "./keys";
import type { WorkspaceListPage } from "@schema/workspaces";

interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
}

function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  const page = options.page ?? WORKSPACE_LIST_DEFAULT_PARAMS.page;
  const pageSize = options.pageSize ?? WORKSPACE_LIST_DEFAULT_PARAMS.pageSize;
  const includeTotal = options.includeTotal ?? WORKSPACE_LIST_DEFAULT_PARAMS.includeTotal;

  return {
    queryKey: workspacesKeys.list({ page, pageSize, includeTotal }),
    queryFn: ({ signal }: { signal?: AbortSignal }) => fetchWorkspaces({ page, pageSize, includeTotal, signal }),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  };
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  const queryClient = useQueryClient();
  const queryOptions = workspacesListQueryOptions(options);
  const initialData = queryClient.getQueryData<WorkspaceListPage>(queryOptions.queryKey);
  return useQuery<WorkspaceListPage>({ ...queryOptions, initialData });
}

