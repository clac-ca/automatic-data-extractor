import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaces } from "@api/workspaces/api";
import { WORKSPACE_LIST_DEFAULT_PARAMS, workspacesKeys } from "./keys";
import type { WorkspaceListPage } from "@schema/workspaces";
import type { FilterItem, FilterJoinOperator } from "@api/listing";
import { useCursorPager } from "@hooks/use-cursor-pager";

interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
  readonly sort?: string | null;
  readonly q?: string | null;
  readonly filters?: FilterItem[];
  readonly joinOperator?: FilterJoinOperator;
  readonly includeTotal?: boolean;
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  const queryClient = useQueryClient();
  const page = options.page ?? WORKSPACE_LIST_DEFAULT_PARAMS.page;
  const pageSize = options.pageSize ?? WORKSPACE_LIST_DEFAULT_PARAMS.pageSize;
  const sort = options.sort ?? WORKSPACE_LIST_DEFAULT_PARAMS.sort;
  const q = options.q ?? WORKSPACE_LIST_DEFAULT_PARAMS.q;
  const filters = options.filters ?? [];
  const joinOperator = options.joinOperator ?? null;
  const includeTotal = options.includeTotal ?? true;

  const filtersKey = useMemo(
    () => (filters.length > 0 ? JSON.stringify(filters) : ""),
    [filters],
  );
  const cursorKey = useMemo(
    () =>
      [
        pageSize,
        sort ?? "",
        q ?? "",
        filtersKey,
        joinOperator ?? "",
        includeTotal ? "total" : "no-total",
      ].join("|"),
    [pageSize, sort, q, filtersKey, joinOperator, includeTotal],
  );

  const cursorPager = useCursorPager({
    page,
    limit: pageSize,
    includeTotal,
    resetKey: cursorKey,
    fetchPage: ({ cursor, limit, includeTotal: includeTotalForPage, signal }) =>
      fetchWorkspaces({
        limit,
        cursor,
        sort: sort ?? undefined,
        q: q ?? undefined,
        filters: filters.length > 0 ? filters : undefined,
        joinOperator: joinOperator ?? undefined,
        includeTotal: includeTotalForPage,
        signal,
      }),
  });

  const queryKey = workspacesKeys.list({
    page,
    pageSize,
    sort,
    q,
    filtersKey: filters.length > 0 ? JSON.stringify(filters) : null,
    joinOperator,
  });

  const initialData = queryClient.getQueryData<WorkspaceListPage>(queryKey);

  return useQuery<WorkspaceListPage>({
    queryKey,
    queryFn: ({ signal }) => cursorPager.fetchCurrentPage(signal),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
    initialData,
  });
}
