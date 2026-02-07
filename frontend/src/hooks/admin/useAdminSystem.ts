import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSsoProvider,
  deleteSsoProvider,
  listSsoProviders,
  readSafeModeStatus,
  readSsoSettings,
  updateSafeModeStatus,
  updateSsoProvider,
  updateSsoSettings,
  type SafeModeStatus,
  type SafeModeUpdateRequest,
  type SsoProviderAdmin,
  type SsoProviderCreateRequest,
  type SsoProviderListResponse,
  type SsoProviderUpdateRequest,
  type SsoSettings,
} from "@/api/admin/sso";
import { adminKeys } from "@/hooks/admin/keys";

export function useSsoProvidersQuery(options: { enabled?: boolean } = {}) {
  return useQuery<SsoProviderListResponse>({
    queryKey: adminKeys.ssoProviders(),
    queryFn: ({ signal }) => listSsoProviders({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useSsoSettingsQuery(options: { enabled?: boolean } = {}) {
  return useQuery<SsoSettings>({
    queryKey: adminKeys.ssoSettings(),
    queryFn: ({ signal }) => readSsoSettings({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useSafeModeQuery(options: { enabled?: boolean } = {}) {
  return useQuery<SafeModeStatus>({
    queryKey: adminKeys.safeMode(),
    queryFn: ({ signal }) => readSafeModeStatus({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<SsoProviderAdmin, Error, SsoProviderCreateRequest>({
    mutationFn: (payload) => createSsoProvider(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.ssoProviders() });
    },
  });
}

export function useUpdateSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<SsoProviderAdmin, Error, { id: string; payload: SsoProviderUpdateRequest }>({
    mutationFn: ({ id, payload }) => updateSsoProvider(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.ssoProviders() });
    },
  });
}

export function useDeleteSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => deleteSsoProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.ssoProviders() });
    },
  });
}

export function useUpdateSsoSettingsMutation() {
  const queryClient = useQueryClient();
  return useMutation<SsoSettings, Error, SsoSettings>({
    mutationFn: (payload) => updateSsoSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.ssoSettings() });
    },
  });
}

export function useUpdateSafeModeMutation() {
  const queryClient = useQueryClient();
  return useMutation<SafeModeStatus, Error, SafeModeUpdateRequest>({
    mutationFn: (payload) => updateSafeModeStatus(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.safeMode() });
    },
  });
}
