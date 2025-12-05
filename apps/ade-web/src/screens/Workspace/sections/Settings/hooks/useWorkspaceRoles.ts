import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { collectAllPages, MAX_PAGE_SIZE } from "@shared/api/pagination";

import {
  workspacesKeys,
  createWorkspaceRole,
  deleteWorkspaceRole,
  listPermissions,
  listWorkspaceRoles,
  updateWorkspaceRole,
  type PermissionListPage,
  type RoleDefinition,
  type RoleListPage,
  type RoleCreatePayload,
  type RoleUpdatePayload,
} from "@features/Workspace/api/workspaces-api";

const ROLE_PAGE_SIZE = MAX_PAGE_SIZE;
const PERMISSION_PAGE_SIZE = MAX_PAGE_SIZE;

const roleListParams = {
  page: 1,
  pageSize: ROLE_PAGE_SIZE,
  includeTotal: true,
} as const;

const permissionListParams = {
  scope: "workspace" as const,
  page: 1,
  pageSize: PERMISSION_PAGE_SIZE,
  includeTotal: false,
} as const;

export function useWorkspaceRolesQuery(workspaceId: string) {
  return useQuery<RoleListPage>({
    queryKey: workspacesKeys.roles(workspaceId, roleListParams),
    queryFn: ({ signal }) =>
      collectAllPages((page) =>
        listWorkspaceRoles({
          page,
          pageSize: ROLE_PAGE_SIZE,
          includeTotal: page === 1,
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
          includeTotal: page === 1,
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
}

export function useUpdateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId, roleListParams);

  return useMutation<RoleDefinition, Error, UpdateRoleInput>({
    mutationFn: ({ roleId, payload }: UpdateRoleInput) => updateWorkspaceRole(workspaceId, roleId, payload),
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

  return useMutation<void, Error, string>({
    mutationFn: (roleId: string) => deleteWorkspaceRole(workspaceId, roleId),
    onSuccess: (_data, roleId) => {
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
      page_size: ROLE_PAGE_SIZE,
      has_next: false,
      has_previous: false,
      total: 1,
    };
  }
  return {
    ...page,
    items: [role, ...page.items],
    total: typeof page.total === "number" ? page.total + 1 : page.total,
    has_next: false,
    has_previous: false,
  };
}
