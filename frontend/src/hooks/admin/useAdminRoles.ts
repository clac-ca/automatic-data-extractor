import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import { adminKeys } from "@/hooks/admin/keys";

const ROLE_PAGE_SIZE = MAX_PAGE_SIZE;
const PERMISSION_PAGE_SIZE = MAX_PAGE_SIZE;

export function useAdminRolesQuery(scope: "global" | "workspace" = "global") {
  return useQuery<AdminRolePage>({
    queryKey: adminKeys.rolesList({ scope, limit: ROLE_PAGE_SIZE }),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminRoles({
          limit: ROLE_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useAdminPermissionsQuery(scope: "global" | "workspace" = "global") {
  return useQuery<AdminPermissionPage>({
    queryKey: adminKeys.permissions(scope),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listAdminPermissions({
          scope,
          limit: PERMISSION_PAGE_SIZE,
          cursor,
          includeTotal: true,
          signal,
        }),
      ),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useAdminUserRolesQuery(userId: string | null | undefined) {
  return useQuery<AdminUserRoles>({
    queryKey: adminKeys.userRoles(userId ?? ""),
    queryFn: ({ signal }) => listAdminUserRoles(userId ?? "", { signal }),
    enabled: Boolean(userId),
    staleTime: 15_000,
    placeholderData: (previous: AdminUserRoles | undefined) => previous,
  });
}

export function useCreateAdminRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminRole, Error, AdminRoleCreateRequest>({
    mutationFn: (payload) => createAdminRole(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.roles() });
    },
  });
}

export function useUpdateAdminRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminRole, Error, { roleId: string; payload: AdminRoleUpdateRequest; ifMatch?: string | null }>({
    mutationFn: ({ roleId, payload, ifMatch }) => updateAdminRole(roleId, payload, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.roles() });
    },
  });
}

export function useDeleteAdminRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { roleId: string; ifMatch?: string | null }>({
    mutationFn: ({ roleId, ifMatch }) => deleteAdminRole(roleId, { ifMatch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.roles() });
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

export function useAssignAdminUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserRoles, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => assignAdminUserRole(userId, roleId),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.userRoles(vars.userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

export function useRemoveAdminUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => removeAdminUserRole(userId, roleId),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.userRoles(vars.userId) });
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}
