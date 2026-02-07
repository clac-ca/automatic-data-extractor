import { useCallback } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useFlattenedPages } from "@/api/pagination";
import {
  createAdminUserApiKey,
  listAdminUserApiKeys,
  listTenantApiKeys,
  revokeAdminUserApiKey,
  type AdminApiKeyListOptions,
} from "@/api/admin/api-keys";
import type { ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyPage, ApiKeySummary } from "@/types";
import { adminKeys } from "@/hooks/admin/keys";

export interface UseTenantApiKeysQueryOptions {
  readonly enabled?: boolean;
  readonly pageSize?: number;
  readonly search?: string;
  readonly includeRevoked?: boolean;
  readonly userId?: string | null;
}

export function useTenantApiKeysQuery(options: UseTenantApiKeysQueryOptions = {}) {
  const {
    enabled = true,
    pageSize,
    search = "",
    includeRevoked = false,
    userId = null,
  } = options;

  const trimmedSearch = search.trim();
  const effectiveSearch = trimmedSearch.length >= 2 ? trimmedSearch : "";

  const query = useInfiniteQuery<ApiKeyPage, Error>({
    queryKey: adminKeys.apiKeysList({ pageSize, search: trimmedSearch, includeRevoked, userId }),
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) =>
      listTenantApiKeys({
        limit: pageSize,
        cursor: typeof pageParam === "string" ? pageParam : null,
        q: effectiveSearch || null,
        includeRevoked,
        includeTotal: true,
        userId,
        signal,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.meta.hasMore ? lastPage.meta.nextCursor ?? undefined : undefined,
    enabled,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const getApiKeyId = useCallback((item: ApiKeySummary) => item.id, []);
  const apiKeys = useFlattenedPages(query.data?.pages, getApiKeyId);
  const total = query.data?.pages?.[0]?.meta.totalCount ?? apiKeys.length;

  return {
    ...query,
    apiKeys,
    total,
  };
}

export function useAdminUserApiKeysQuery(userId: string | null | undefined, options: AdminApiKeyListOptions = {}) {
  return useQuery<ApiKeyPage>({
    queryKey: adminKeys.userApiKeys(userId ?? ""),
    queryFn: ({ signal }) =>
      listAdminUserApiKeys(userId ?? "", {
        ...options,
        includeTotal: true,
        signal,
      }),
    enabled: Boolean(userId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateAdminUserApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<ApiKeyCreateResponse, Error, { userId: string; payload: ApiKeyCreateRequest }>({
    mutationFn: ({ userId, payload }) => createAdminUserApiKey(userId, payload),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.userApiKeys(vars.userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.apiKeys() });
    },
  });
}

export function useRevokeAdminUserApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { userId: string; apiKeyId: string; ifMatch?: string | null }>({
    mutationFn: ({ userId, apiKeyId, ifMatch }) => revokeAdminUserApiKey(userId, apiKeyId, { ifMatch }),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.userApiKeys(vars.userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.apiKeys() });
    },
  });
}
