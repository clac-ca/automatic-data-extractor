import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSsoProvider,
  deleteSsoProvider,
  listSsoProviders,
  validateSsoProvider,
  updateSsoProvider,
  type SsoProviderAdmin,
  type SsoProviderCreateRequest,
  type SsoProviderListResponse,
  type SsoProviderUpdateRequest,
  type SsoProviderValidateRequest,
  type SsoProviderValidationResponse,
} from "@/api/admin/sso";
import {
  createScimToken,
  listScimTokens,
  revokeScimToken,
  type ScimTokenCreateRequest,
  type ScimTokenCreateResponse,
  type ScimTokenListResponse,
  type ScimTokenOut,
} from "@/api/admin/scim";
import {
  patchAdminSettings,
  readAdminSettings,
  type AdminSettingsPatchRequest,
  type AdminSettingsReadResponse,
} from "@/api/admin/settings";
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

export function useAdminSettingsQuery(options: { enabled?: boolean } = {}) {
  return useQuery<AdminSettingsReadResponse>({
    queryKey: adminKeys.settings(),
    queryFn: ({ signal }) => readAdminSettings({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useScimTokensQuery(options: { enabled?: boolean } = {}) {
  return useQuery<ScimTokenListResponse>({
    queryKey: adminKeys.scimTokens(),
    queryFn: ({ signal }) => listScimTokens({ signal }),
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

export function useValidateSsoProviderMutation() {
  return useMutation<SsoProviderValidationResponse, Error, SsoProviderValidateRequest>({
    mutationFn: (payload) => validateSsoProvider(payload),
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

export function usePatchAdminSettingsMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminSettingsReadResponse, Error, AdminSettingsPatchRequest>({
    mutationFn: (payload) => patchAdminSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(adminKeys.settings(), data);
      queryClient.invalidateQueries({ queryKey: adminKeys.settings() });
    },
  });
}

export function useCreateScimTokenMutation() {
  const queryClient = useQueryClient();
  return useMutation<ScimTokenCreateResponse, Error, ScimTokenCreateRequest>({
    mutationFn: (payload) => createScimToken(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.scimTokens() });
    },
  });
}

export function useRevokeScimTokenMutation() {
  const queryClient = useQueryClient();
  return useMutation<ScimTokenOut, Error, string>({
    mutationFn: (tokenId) => revokeScimToken(tokenId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.scimTokens() });
    },
  });
}
