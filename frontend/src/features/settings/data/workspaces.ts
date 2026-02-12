import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createInvitation, type Invitation, type InvitationCreateRequest, listInvitations, cancelInvitation, resendInvitation } from "@/api/invitations/api";
import { collectAllPages, MAX_PAGE_SIZE } from "@/api/pagination";
import {
  addWorkspacePrincipalRoles,
  createWorkspaceRole,
  deleteWorkspace,
  deleteWorkspaceRole,
  fetchWorkspaces,
  listPermissions,
  listWorkspacePrincipals,
  listWorkspaceRoles,
  removeWorkspacePrincipal,
  updateWorkspace,
  updateWorkspacePrincipalRoles,
  updateWorkspaceRole,
} from "@/api/workspaces/api";
import { fetchUsers, type UserListPage, type UserSummary } from "@/api/users/api";
import { listGroups, type Group } from "@/api/groups/api";
import type {
  PermissionListPage,
  RoleCreatePayload,
  RoleDefinition,
  RoleListPage,
  RoleUpdatePayload,
  WorkspaceListPage,
  WorkspaceProfile,
  WorkspacePrincipal,
  WorkspaceUpdatePayload,
  WorkspacePrincipalType,
} from "@/types/workspaces";

import { settingsKeys } from "./keys";

const SETTINGS_PAGE_SIZE = MAX_PAGE_SIZE;

function normalizeSearch(search: string) {
  const trimmed = search.trim();
  return trimmed.length >= 2 ? trimmed : "";
}

export function useSettingsWorkspacesListQuery() {
  return useQuery<WorkspaceListPage, Error>({
    queryKey: settingsKeys.workspacesList(),
    queryFn: ({ signal }) =>
      fetchWorkspaces({
        limit: SETTINGS_PAGE_SIZE,
        includeTotal: true,
        signal,
      }),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useSettingsWorkspaceDetailQuery(workspaceId: string | null) {
  return useQuery<WorkspaceProfile | null, Error>({
    queryKey: settingsKeys.workspaceDetail(workspaceId ?? ""),
    queryFn: async ({ signal }) => {
      const page = await fetchWorkspaces({ limit: SETTINGS_PAGE_SIZE, includeTotal: true, signal });
      return page.items.find((workspace) => workspace.id === workspaceId) ?? null;
    },
    enabled: Boolean(workspaceId),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useUpdateSettingsWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<WorkspaceProfile, Error, WorkspaceUpdatePayload>({
    mutationFn: (payload) => updateWorkspace(workspaceId, payload),
    onSuccess: (workspace) => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaces() });
      queryClient.setQueryData(settingsKeys.workspaceDetail(workspace.id), workspace);
    },
  });
}

export function useDeleteSettingsWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => deleteWorkspace(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaces() });
    },
  });
}

export function useWorkspaceRolesListQuery(workspaceId: string | null) {
  return useQuery<RoleListPage, Error>({
    queryKey: settingsKeys.workspaceRoles(workspaceId ?? ""),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listWorkspaceRoles({
          limit: SETTINGS_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    enabled: Boolean(workspaceId),
    staleTime: 20_000,
    placeholderData: (previous) => previous,
  });
}

export function useWorkspaceRolePermissionsQuery() {
  return useQuery<PermissionListPage, Error>({
    queryKey: settingsKeys.workspaceRolePermissions(),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listPermissions({
          scope: "workspace",
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

export function useWorkspaceRoleDetailQuery(workspaceId: string | null, roleId: string | null) {
  const listQuery = useWorkspaceRolesListQuery(workspaceId);
  return {
    ...listQuery,
    data: roleId ? listQuery.data?.items.find((role) => role.id === roleId) ?? null : null,
  };
}

export function useCreateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<RoleDefinition, Error, RoleCreatePayload>({
    mutationFn: (payload) => createWorkspaceRole(workspaceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceRoles(workspaceId) });
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useUpdateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<
    RoleDefinition,
    Error,
    { roleId: string; payload: RoleUpdatePayload; ifMatch?: string | null }
  >({
    mutationFn: ({ roleId, payload, ifMatch }) => updateWorkspaceRole(workspaceId, roleId, payload, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceRoles(workspaceId) });
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useDeleteWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { roleId: string; ifMatch?: string | null }>({
    mutationFn: ({ roleId, ifMatch }) => deleteWorkspaceRole(workspaceId, roleId, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceRoles(workspaceId) });
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useWorkspacePrincipalsListQuery(workspaceId: string | null) {
  return useQuery<{ items: WorkspacePrincipal[] }, Error>({
    queryKey: settingsKeys.workspacePrincipals(workspaceId ?? ""),
    queryFn: ({ signal }) => listWorkspacePrincipals(workspaceId ?? "", { limit: SETTINGS_PAGE_SIZE, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useWorkspacePrincipalDetailQuery(
  workspaceId: string | null,
  principalType: WorkspacePrincipalType | null,
  principalId: string | null,
) {
  const listQuery = useWorkspacePrincipalsListQuery(workspaceId);
  return {
    ...listQuery,
    data:
      principalType && principalId
        ? listQuery.data?.items.find(
            (item) => item.principal_type === principalType && item.principal_id === principalId,
          ) ?? null
        : null,
  };
}

export interface WorkspacePrincipalCreateInput {
  readonly principalType: WorkspacePrincipalType;
  readonly principalId: string;
  readonly roleIds: readonly string[];
}

export function useCreateWorkspacePrincipalMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<WorkspacePrincipal, Error, WorkspacePrincipalCreateInput>({
    mutationFn: ({ principalType, principalId, roleIds }) =>
      addWorkspacePrincipalRoles(workspaceId, {
        principal_type: principalType,
        principal_id: principalId,
        role_ids: Array.from(roleIds),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useUpdateWorkspacePrincipalMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<
    WorkspacePrincipal | null,
    Error,
    { principalType: WorkspacePrincipalType; principalId: string; roleIds: readonly string[] }
  >({
    mutationFn: ({ principalType, principalId, roleIds }) =>
      updateWorkspacePrincipalRoles(workspaceId, principalType, principalId, {
        role_ids: Array.from(roleIds),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useRemoveWorkspacePrincipalMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { principalType: WorkspacePrincipalType; principalId: string }>({
    mutationFn: ({ principalType, principalId }) =>
      removeWorkspacePrincipal(workspaceId, principalType, principalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useWorkspaceInvitationsListQuery(workspaceId: string | null) {
  return useQuery<{ items: Invitation[] }, Error>({
    queryKey: settingsKeys.workspaceInvitations(workspaceId ?? ""),
    queryFn: ({ signal }) => listInvitations({ workspaceId: workspaceId ?? undefined, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useWorkspaceInvitationDetailQuery(workspaceId: string | null, invitationId: string | null) {
  const listQuery = useWorkspaceInvitationsListQuery(workspaceId);
  return {
    ...listQuery,
    data:
      invitationId == null
        ? null
        : listQuery.data?.items.find((invitation) => invitation.id === invitationId) ?? null,
  };
}

export function useCreateWorkspaceInvitationMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<Invitation, Error, InvitationCreateRequest>({
    mutationFn: (payload) => createInvitation(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceInvitations(workspaceId) });
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspacePrincipals(workspaceId) });
    },
  });
}

export function useResendWorkspaceInvitationMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<Invitation, Error, string>({
    mutationFn: (invitationId) => resendInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceInvitations(workspaceId) });
    },
  });
}

export function useCancelWorkspaceInvitationMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<Invitation, Error, string>({
    mutationFn: (invitationId) => cancelInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.workspaceInvitations(workspaceId) });
    },
  });
}

export function useUsersLookupQuery(search: string, enabled = true) {
  const effectiveSearch = normalizeSearch(search);
  return useQuery<UserListPage, Error>({
    queryKey: settingsKeys.usersLookup(effectiveSearch),
    queryFn: ({ signal }) =>
      fetchUsers({
        search: effectiveSearch,
        limit: SETTINGS_PAGE_SIZE,
        includeTotal: true,
        signal,
      }),
    enabled: enabled && effectiveSearch.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useGroupsLookupQuery(search: string, enabled = true) {
  const effectiveSearch = normalizeSearch(search);
  return useQuery<{ items: Group[] }, Error>({
    queryKey: settingsKeys.groupsLookup(effectiveSearch),
    queryFn: ({ signal }) => listGroups({ q: effectiveSearch || undefined, signal }),
    enabled,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function findUser(users: readonly UserSummary[] | undefined, userId: string) {
  return users?.find((user) => user.id === userId) ?? null;
}

export function findGroup(groups: readonly Group[] | undefined, groupId: string) {
  return groups?.find((group) => group.id === groupId) ?? null;
}
