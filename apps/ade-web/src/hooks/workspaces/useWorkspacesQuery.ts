import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaces } from "@api/workspaces/api";
import { WORKSPACE_LIST_DEFAULT_PARAMS, workspacesKeys } from "./keys";
import type { WorkspaceListPage } from "@schema/workspaces";
import type { FilterItem, FilterJoinOperator } from "@api/listing";

interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
  readonly sort?: string | null;
  readonly q?: string | null;
  readonly filters?: FilterItem[];
  readonly joinOperator?: FilterJoinOperator;
}

function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  const page = options.page ?? WORKSPACE_LIST_DEFAULT_PARAMS.page;
  const pageSize = options.pageSize ?? WORKSPACE_LIST_DEFAULT_PARAMS.pageSize;
  const sort = options.sort ?? WORKSPACE_LIST_DEFAULT_PARAMS.sort;
  const q = options.q ?? WORKSPACE_LIST_DEFAULT_PARAMS.q;
  const filters = options.filters ?? [];
  const joinOperator = options.joinOperator ?? null;

  return {
    queryKey: workspacesKeys.list({
      page,
      pageSize,
      sort,
      q,
      filtersKey: filters.length > 0 ? JSON.stringify(filters) : null,
      joinOperator,
    }),
    queryFn: ({ signal }: { signal?: AbortSignal }) =>
      fetchWorkspaces({
        page,
        pageSize,
        sort: sort ?? undefined,
        q: q ?? undefined,
        filters: filters.length > 0 ? filters : undefined,
        joinOperator: joinOperator ?? undefined,
        signal,
      }),
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
