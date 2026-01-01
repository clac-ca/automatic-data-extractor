import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { collectAllPages, MAX_PAGE_SIZE } from "@api/pagination";

import {
  createWorkspaceRole,
  deleteWorkspaceRole,
  listPermissions,
  listWorkspaceRoles,
  updateWorkspaceRole,
} from "@api/workspaces/api";
import { workspacesKeys } from "@hooks/workspaces";
import type {
  PermissionListPage,
  RoleCreatePayload,
  RoleDefinition,
  RoleListPage,
  RoleUpdatePayload,
} from "@schema/workspaces";

const ROLE_PAGE_SIZE = MAX_PAGE_SIZE;
const PERMISSION_PAGE_SIZE = MAX_PAGE_SIZE;

const roleListParams = {
  page: 1,
  pageSize: ROLE_PAGE_SIZE,
} as const;

const permissionListParams = {
  scope: "workspace" as const,
  page: 1,
  pageSize: PERMISSION_PAGE_SIZE,
} as const;

export function useWorkspaceRolesQuery(workspaceId: string) {
  return useQuery<RoleListPage>({
    queryKey: workspacesKeys.roles(workspaceId, roleListParams),
    queryFn: ({ signal }) =>
      collectAllPages((page) =>
        listWorkspaceRoles({
          page,
          pageSize: ROLE_PAGE_SIZE,
          signal,
        }),
      ),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function usePermissionsQuery(scope: "workspace" | "global" = "workspace") {
  const params = { ...permissionListParams, scope };
  return useQuery<PermissionListPage>({
    queryKey: workspacesKeys.permissions(params),
    queryFn: ({ signal }) =>
      collectAllPages((page) =>
        listPermissions({
          scope,
          page,
          pageSize: params.pageSize,
          signal,
        }),
      ),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId, roleListParams);

  return useMutation<RoleDefinition, Error, RoleCreatePayload>({
    mutationFn: (payload: RoleCreatePayload) => createWorkspaceRole(workspaceId, payload),
    onSuccess: (role) => {
      queryClient.setQueryData<RoleListPage>(queryKey, (current) => appendRole(current, role));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

interface UpdateRoleInput {
  readonly roleId: string;
  readonly payload: RoleUpdatePayload;
  readonly ifMatch?: string | null;
}

export function useUpdateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId, roleListParams);

  return useMutation<RoleDefinition, Error, UpdateRoleInput>({
    mutationFn: ({ roleId, payload, ifMatch }: UpdateRoleInput) =>
      updateWorkspaceRole(workspaceId, roleId, payload, { ifMatch }),
    onSuccess: (role) => {
      queryClient.setQueryData<RoleListPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((entry) => (entry.id === role.id ? role : entry)),
        };
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useDeleteWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId, roleListParams);

  return useMutation<void, Error, { roleId: string; ifMatch?: string | null }>({
    mutationFn: ({ roleId, ifMatch }) => deleteWorkspaceRole(workspaceId, roleId, { ifMatch }),
    onSuccess: (_data, { roleId }) => {
      queryClient.setQueryData<RoleListPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        const items = current.items.filter((role) => role.id !== roleId);
        return {
          ...current,
          items,
          total: typeof current.total === "number" ? Math.max(current.total - 1, 0) : current.total,
        };
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

function appendRole(page: RoleListPage | undefined, role: RoleDefinition): RoleListPage | undefined {
  if (!page) {
    return {
      items: [role],
      page: 1,
      perPage: ROLE_PAGE_SIZE,
      pageCount: 1,
      total: 1,
      changesCursor: "0",
    };
  }
  return {
    ...page,
    items: [role, ...page.items],
    total: page.total + 1,
    pageCount: 1,
  };
}
