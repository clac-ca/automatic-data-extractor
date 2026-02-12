import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addGroupMember,
  addGroupOwner,
  createGroup,
  deleteGroup,
  listGroupMembers,
  listGroupOwners,
  listGroups,
  removeGroupMember,
  removeGroupOwner,
  updateGroup,
  type Group,
  type GroupCreateRequest,
  type GroupUpdateRequest,
} from "@/api/groups/api";
import { collectAllPages, MAX_PAGE_SIZE } from "@/api/pagination";
import {
  assignAdminUserRole,
  createAdminRole,
  deleteAdminRole,
  listAdminPermissions,
  listAdminRoles,
  listAdminUserRoles,
  removeAdminUserRole,
  updateAdminRole,
  type AdminPermissionPage,
  type AdminRole,
  type AdminRoleCreateRequest,
  type AdminRolePage,
  type AdminRoleUpdateRequest,
  type AdminUserRoles,
} from "@/api/admin/roles";
import {
  createAdminUser,
  deactivateAdminUser,
  getAdminUser,
  listAdminUserMemberOf,
  listAdminUsers,
  removeAdminUserMemberOf,
  addAdminUserMemberOf,
  updateAdminUser,
  type AdminUser,
  type AdminUserCreateRequest,
  type AdminUserCreateResponse,
  type AdminUserMemberOf,
  type AdminUserPage,
  type AdminUserUpdateRequest,
} from "@/api/admin/users";
import {
  createAdminUserApiKey,
  listAdminUserApiKeys,
  listTenantApiKeys,
  revokeAdminUserApiKey,
} from "@/api/admin/api-keys";
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
  createSsoProvider,
  deleteSsoProvider,
  listSsoProviders,
  updateSsoProvider,
  validateSsoProvider,
  type SsoProviderAdmin,
  type SsoProviderCreateRequest,
  type SsoProviderListResponse,
  type SsoProviderUpdateRequest,
  type SsoProviderValidateRequest,
  type SsoProviderValidationResponse,
} from "@/api/admin/sso";
import {
  patchAdminSettings,
  readAdminSettings,
  type AdminSettingsPatchRequest,
  type AdminSettingsReadResponse,
} from "@/api/admin/settings";
import type { ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyPage } from "@/types";

import { settingsKeys } from "./keys";

const SETTINGS_PAGE_SIZE = MAX_PAGE_SIZE;

function normalizeSearch(search: string) {
  const trimmed = search.trim();
  return trimmed.length >= 2 ? trimmed : "";
}

export function useOrganizationUsersListQuery(search: string) {
  const effectiveSearch = normalizeSearch(search);
  return useQuery<AdminUserPage, Error>({
    queryKey: settingsKeys.organizationUsersList(effectiveSearch),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminUsers({
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          search: effectiveSearch || undefined,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationUserDetailQuery(userId: string | null) {
  return useQuery<AdminUser, Error>({
    queryKey: settingsKeys.organizationUserDetail(userId ?? ""),
    queryFn: ({ signal }) => getAdminUser(userId ?? "", { signal }),
    enabled: Boolean(userId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationUserMemberOfQuery(userId: string | null) {
  return useQuery<AdminUserMemberOf, Error>({
    queryKey: settingsKeys.organizationUserMemberOf(userId ?? ""),
    queryFn: ({ signal }) => listAdminUserMemberOf(userId ?? "", { signal }),
    enabled: Boolean(userId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationUserRolesQuery(userId: string | null) {
  return useQuery<AdminUserRoles, Error>({
    queryKey: settingsKeys.organizationUserRoles(userId ?? ""),
    queryFn: ({ signal }) => listAdminUserRoles(userId ?? "", { signal }),
    enabled: Boolean(userId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationUserApiKeysQuery(userId: string | null) {
  return useQuery<ApiKeyPage, Error>({
    queryKey: settingsKeys.organizationUserApiKeys(userId ?? ""),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminUserApiKeys(userId ?? "", {
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          includeRevoked: true,
          includeTotal: true,
          signal,
        }),
      ),
    enabled: Boolean(userId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateOrganizationUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserCreateResponse, Error, AdminUserCreateRequest>({
    mutationFn: (payload) => createAdminUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useUpdateOrganizationUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, { userId: string; payload: AdminUserUpdateRequest }>({
    mutationFn: ({ userId, payload }) => updateAdminUser(userId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserDetail(variables.userId),
      });
    },
  });
}

export function useDeactivateOrganizationUserMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, string>({
    mutationFn: (userId) => deactivateAdminUser(userId),
    onSuccess: (_data, userId) => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUserDetail(userId) });
    },
  });
}

export function useAssignOrganizationUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserRoles, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => assignAdminUserRole(userId, roleId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserRoles(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useRemoveOrganizationUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => removeAdminUserRole(userId, roleId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserRoles(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useAddOrganizationUserMemberOfMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserMemberOf, Error, { userId: string; groupId: string }>({
    mutationFn: ({ userId, groupId }) => addAdminUserMemberOf(userId, groupId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserMemberOf(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationGroups() });
    },
  });
}

export function useRemoveOrganizationUserMemberOfMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { userId: string; groupId: string }>({
    mutationFn: ({ userId, groupId }) => removeAdminUserMemberOf(userId, groupId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserMemberOf(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationGroups() });
    },
  });
}

export function useCreateOrganizationUserApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    ApiKeyCreateResponse,
    Error,
    { userId: string; payload: ApiKeyCreateRequest }
  >({
    mutationFn: ({ userId, payload }) => createAdminUserApiKey(userId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserApiKeys(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationApiKeys() });
    },
  });
}

export function useRevokeOrganizationUserApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    void,
    Error,
    { userId: string; apiKeyId: string; ifMatch?: string | null }
  >({
    mutationFn: ({ userId, apiKeyId, ifMatch }) => revokeAdminUserApiKey(userId, apiKeyId, { ifMatch }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationUserApiKeys(variables.userId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationApiKeys() });
    },
  });
}

export function useOrganizationGroupsListQuery(search: string) {
  const effectiveSearch = normalizeSearch(search);
  return useQuery<{ items: Group[] }, Error>({
    queryKey: settingsKeys.organizationGroupsList(effectiveSearch),
    queryFn: ({ signal }) => listGroups({ q: effectiveSearch || undefined, signal }),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationGroupDetailQuery(groupId: string | null) {
  return useQuery<Group | null, Error>({
    queryKey: [...settingsKeys.organizationGroups(), "detail", groupId ?? ""],
    queryFn: async ({ signal }) => {
      const list = await listGroups({ signal });
      return list.items.find((group) => group.id === groupId) ?? null;
    },
    enabled: Boolean(groupId),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationGroupMembersQuery(groupId: string | null) {
  return useQuery({
    queryKey: settingsKeys.organizationGroupMembers(groupId ?? ""),
    queryFn: () => listGroupMembers(groupId ?? ""),
    enabled: Boolean(groupId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationGroupOwnersQuery(groupId: string | null) {
  return useQuery({
    queryKey: settingsKeys.organizationGroupOwners(groupId ?? ""),
    queryFn: () => listGroupOwners(groupId ?? ""),
    enabled: Boolean(groupId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateOrganizationGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation<Group, Error, GroupCreateRequest>({
    mutationFn: (payload) => createGroup(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationGroups() });
    },
  });
}

export function useUpdateOrganizationGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation<Group, Error, { groupId: string; payload: GroupUpdateRequest }>({
    mutationFn: ({ groupId, payload }) => updateGroup(groupId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationGroups() });
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupMembers(variables.groupId),
      });
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupOwners(variables.groupId),
      });
    },
  });
}

export function useDeleteOrganizationGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (groupId) => deleteGroup(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationGroups() });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useAddOrganizationGroupMemberMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      addGroupMember(groupId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupMembers(variables.groupId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useRemoveOrganizationGroupMemberMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      removeGroupMember(groupId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupMembers(variables.groupId),
      });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useAddOrganizationGroupOwnerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      addGroupOwner(groupId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupOwners(variables.groupId),
      });
    },
  });
}

export function useRemoveOrganizationGroupOwnerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      removeGroupOwner(groupId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.organizationGroupOwners(variables.groupId),
      });
    },
  });
}

export function useOrganizationRolesListQuery() {
  return useQuery<AdminRolePage, Error>({
    queryKey: settingsKeys.organizationRolesList(),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminRoles({
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useOrganizationRoleDetailQuery(roleId: string | null) {
  const rolesQuery = useOrganizationRolesListQuery();
  return {
    ...rolesQuery,
    data:
      roleId == null
        ? null
        : (rolesQuery.data?.items.find((role) => role.id === roleId) ?? null),
  };
}

export function useOrganizationPermissionsQuery(scope: "global" | "workspace" = "global") {
  return useQuery<AdminPermissionPage, Error>({
    queryKey: settingsKeys.organizationPermissions(scope),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminPermissions({
          scope,
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateOrganizationRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminRole, Error, AdminRoleCreateRequest>({
    mutationFn: (payload) => createAdminRole(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationRoles() });
    },
  });
}

export function useUpdateOrganizationRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    AdminRole,
    Error,
    { roleId: string; payload: AdminRoleUpdateRequest; ifMatch?: string | null }
  >({
    mutationFn: ({ roleId, payload, ifMatch }) => updateAdminRole(roleId, payload, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationRoles() });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useDeleteOrganizationRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { roleId: string; ifMatch?: string | null }>({
    mutationFn: ({ roleId, ifMatch }) => deleteAdminRole(roleId, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationRoles() });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useOrganizationApiKeysQuery(includeRevoked: boolean) {
  return useQuery<ApiKeyPage, Error>({
    queryKey: settingsKeys.organizationApiKeysList(includeRevoked),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listTenantApiKeys({
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          includeRevoked,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useRevokeOrganizationApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    void,
    Error,
    { userId: string; apiKeyId: string; ifMatch?: string | null }
  >({
    mutationFn: ({ userId, apiKeyId, ifMatch }) => revokeAdminUserApiKey(userId, apiKeyId, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationApiKeys() });
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationUsers() });
    },
  });
}

export function useOrganizationRuntimeSettingsQuery(enabled = true) {
  return useQuery<AdminSettingsReadResponse, Error>({
    queryKey: settingsKeys.organizationRuntimeSettings(),
    queryFn: ({ signal }) => readAdminSettings({ signal }),
    enabled,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function usePatchOrganizationRuntimeSettingsMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminSettingsReadResponse, Error, AdminSettingsPatchRequest>({
    mutationFn: (payload) => patchAdminSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(settingsKeys.organizationRuntimeSettings(), data);
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationRuntimeSettings() });
    },
  });
}

export function useOrganizationSsoProvidersQuery(enabled = true) {
  return useQuery<SsoProviderListResponse, Error>({
    queryKey: settingsKeys.organizationSsoProviders(),
    queryFn: ({ signal }) => listSsoProviders({ signal }),
    enabled,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateOrganizationSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<SsoProviderAdmin, Error, SsoProviderCreateRequest>({
    mutationFn: (payload) => createSsoProvider(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationSsoProviders() });
    },
  });
}

export function useUpdateOrganizationSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    SsoProviderAdmin,
    Error,
    { id: string; payload: SsoProviderUpdateRequest }
  >({
    mutationFn: ({ id, payload }) => updateSsoProvider(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationSsoProviders() });
    },
  });
}

export function useDeleteOrganizationSsoProviderMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => deleteSsoProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationSsoProviders() });
    },
  });
}

export function useValidateOrganizationSsoProviderMutation() {
  return useMutation<SsoProviderValidationResponse, Error, SsoProviderValidateRequest>({
    mutationFn: (payload) => validateSsoProvider(payload),
  });
}

export function useOrganizationScimTokensQuery(enabled = true) {
  return useQuery<ScimTokenListResponse, Error>({
    queryKey: settingsKeys.organizationScimTokens(),
    queryFn: ({ signal }) => listScimTokens({ signal }),
    enabled,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateOrganizationScimTokenMutation() {
  const queryClient = useQueryClient();
  return useMutation<ScimTokenCreateResponse, Error, ScimTokenCreateRequest>({
    mutationFn: (payload) => createScimToken(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationScimTokens() });
    },
  });
}

export function useRevokeOrganizationScimTokenMutation() {
  const queryClient = useQueryClient();
  return useMutation<ScimTokenOut, Error, string>({
    mutationFn: (tokenId) => revokeScimToken(tokenId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.organizationScimTokens() });
    },
  });
}
