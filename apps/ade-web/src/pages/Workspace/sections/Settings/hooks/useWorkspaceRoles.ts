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
  limit: ROLE_PAGE_SIZE,
} as const;

const permissionListParams = {
  scope: "workspace" as const,
  limit: PERMISSION_PAGE_SIZE,
} as const;

export function useWorkspaceRolesQuery(workspaceId: string) {
  return useQuery<RoleListPage>({
    queryKey: workspacesKeys.roles(workspaceId, roleListParams),
    queryFn: ({ signal }) =>
      collectAllPages((cursor) =>
        listWorkspaceRoles({
          limit: ROLE_PAGE_SIZE,
          cursor,
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
      collectAllPages((cursor) =>
        listPermissions({
          scope,
          limit: params.limit,
          cursor,
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
          meta: {
            ...current.meta,
            totalCount:
              typeof current.meta.totalCount === "number"
                ? Math.max(current.meta.totalCount - 1, 0)
                : current.meta.totalCount,
          },
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
      meta: {
        limit: ROLE_PAGE_SIZE,
        hasMore: false,
        nextCursor: null,
        totalIncluded: true,
        totalCount: 1,
        changesCursor: "0",
      },
      facets: null,
    };
  }
  return {
    ...page,
    items: [role, ...page.items],
    meta: {
      ...page.meta,
      totalCount:
        typeof page.meta.totalCount === "number" ? page.meta.totalCount + 1 : page.meta.totalCount,
    },
  };
}
