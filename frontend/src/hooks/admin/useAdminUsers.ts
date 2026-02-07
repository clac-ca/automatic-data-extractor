import { useCallback } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useFlattenedPages } from "@/api/pagination";
import {
  createAdminUser,
  deactivateAdminUser,
  listAdminUsers,
  updateAdminUser,
  type AdminUser,
  type AdminUserCreateRequest,
  type AdminUserPage,
  type AdminUserUpdateRequest,
} from "@/api/admin/users";
import { adminKeys } from "@/hooks/admin/keys";

export interface UseAdminUsersQueryOptions {
  readonly enabled?: boolean;
  readonly search?: string;
  readonly pageSize?: number;
}

export function useAdminUsersQuery(options: UseAdminUsersQueryOptions = {}) {
  const {
    enabled = true,
    search = "",
    pageSize,
  } = options;

  const trimmedSearch = search.trim();
  const effectiveSearch = trimmedSearch.length >= 2 ? trimmedSearch : "";

  const query = useInfiniteQuery<AdminUserPage, Error>({
    queryKey: adminKeys.usersList({ search: trimmedSearch, pageSize }),
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) =>
      listAdminUsers({
        limit: pageSize,
        cursor: typeof pageParam === "string" ? pageParam : null,
        search: effectiveSearch || undefined,
        includeTotal: true,
        signal,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.meta.hasMore ? lastPage.meta.nextCursor ?? undefined : undefined,
    enabled,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const getUserKey = useCallback((user: AdminUser) => user.id, []);
  const users = useFlattenedPages(query.data?.pages, getUserKey);
  const total = query.data?.pages?.[0]?.meta.totalCount ?? users.length;

  return {
    ...query,
    users,
    total,
  };
}

export function useCreateAdminUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, AdminUserCreateRequest>({
    mutationFn: (payload) => createAdminUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

export function useUpdateAdminUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, { userId: string; payload: AdminUserUpdateRequest }>({
    mutationFn: ({ userId, payload }) => updateAdminUser(userId, payload),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.user(vars.userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

export function useDeactivateAdminUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, string>({
    mutationFn: (userId) => deactivateAdminUser(userId),
    onSuccess: (_data, userId) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.user(userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}
