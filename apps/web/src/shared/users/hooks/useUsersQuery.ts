import { useCallback } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";

import { fetchUsers, type FetchUsersOptions, type UserListPage } from "../api";
import { useFlattenedPages } from "@shared/api/pagination";

export interface UseUsersQueryOptions {
  readonly enabled?: boolean;
  readonly search?: string;
  readonly pageSize?: number;
}

export function useUsersQuery(options: UseUsersQueryOptions = {}) {
  const {
    enabled = true,
    search = "",
    pageSize,
  } = options;

  const trimmedSearch = search.trim();
  const effectiveSearch = trimmedSearch.length >= 2 ? trimmedSearch : "";

  const query = useInfiniteQuery<UserListPage, Error>({
    queryKey: ["users", "all", { search: trimmedSearch, pageSize }],
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchUsers(normalizeFetchOptions({
        page: typeof pageParam === "number" ? pageParam : 1,
        pageSize,
        search: effectiveSearch || undefined,
        signal,
      })),
    getNextPageParam: (lastPage) => (lastPage.hasNext ? lastPage.page + 1 : undefined),
    enabled,
    staleTime: 60_000,
  });

  const getUserKey = useCallback((user: UserListPage["items"][number]) => user.user_id, []);
  const users = useFlattenedPages(query.data?.pages, getUserKey);

  return {
    ...query,
    users,
  };
}

function normalizeFetchOptions(options: FetchUsersOptions): FetchUsersOptions {
  const next: FetchUsersOptions = { ...options };
  if (!next.page || next.page < 1) {
    next.page = 1;
  }
  return next;
}

