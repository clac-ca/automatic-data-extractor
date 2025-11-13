import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
} from "@screens/Workspace/api/workspaces-api";

const ROLES_PAGE_SIZE = 200;
const PERMISSIONS_PAGE_SIZE = 200;

export function useWorkspaceRolesQuery(workspaceId: string) {
  const roleListParams = { page: 1, pageSize: ROLES_PAGE_SIZE };
  return useQuery<RoleListPage>({
    queryKey: workspacesKeys.roles(workspaceId, roleListParams),
    queryFn: ({ signal }) =>
      listWorkspaceRoles(workspaceId, { signal, pageSize: ROLES_PAGE_SIZE, includeTotal: true }),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function usePermissionsQuery() {
  const permissionKeyParams = { scope: "global", page: 1, pageSize: PERMISSIONS_PAGE_SIZE };
  return useQuery<PermissionListPage>({
    queryKey: workspacesKeys.permissions(permissionKeyParams),
    queryFn: ({ signal }) =>
      listPermissions({ signal, scope: "global", pageSize: PERMISSIONS_PAGE_SIZE }),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useCreateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId, { page: 1, pageSize: ROLES_PAGE_SIZE });

  return useMutation<RoleDefinition, Error, RoleCreatePayload, { previous?: RoleListPage; optimisticId: string }>({
    mutationFn: (payload: RoleCreatePayload) => createWorkspaceRole(workspaceId, payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleListPage>(queryKey);
      const optimisticRole: RoleDefinition = {
        id: `optimistic-${Date.now()}`,
        slug: payload.slug ?? payload.name.toLowerCase().replace(/\s+/g, "-"),
        name: payload.name,
        description: payload.description ?? null,
        scope_type: "workspace",
        scope_id: workspaceId,
        permissions: Array.from(payload.permissions ?? []),
        built_in: false,
        editable: true,
      };
      queryClient.setQueryData<RoleListPage>(queryKey, (current) =>
        appendRole(current, optimisticRole),
      );
      return { previous, optimisticId: optimisticRole.id };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (role, _variables, context) => {
      queryClient.setQueryData<RoleListPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        if (!context) {
          return appendRole(current, role);
        }
        return {
          ...current,
          items: current.items.map((entry) => (entry.id === context.optimisticId ? role : entry)),
        };
      });
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
  const queryKey = workspacesKeys.roles(workspaceId, { page: 1, pageSize: ROLES_PAGE_SIZE });

  return useMutation<RoleDefinition, Error, UpdateRoleInput, { previous?: RoleListPage }>({
    mutationFn: ({ roleId, payload }: UpdateRoleInput) => updateWorkspaceRole(workspaceId, roleId, payload),
    onMutate: async ({ roleId, payload }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleListPage>(queryKey);
      queryClient.setQueryData<RoleListPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((role) =>
            role.id === roleId
              ? {
                  ...role,
                  name: payload.name,
                  description: payload.description ?? null,
                  permissions: Array.from(payload.permissions ?? []),
                }
              : role,
          ),
        };
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
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
  const queryKey = workspacesKeys.roles(workspaceId, { page: 1, pageSize: ROLES_PAGE_SIZE });

  return useMutation<void, Error, string, { previous?: RoleListPage }>({
    mutationFn: (roleId: string) => deleteWorkspaceRole(workspaceId, roleId),
    onMutate: async (roleId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleListPage>(queryKey);
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
      return { previous };
    },
    onError: (_error, _roleId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
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
      page_size: ROLES_PAGE_SIZE,
      has_next: false,
      has_previous: false,
      total: 1,
    };
  }
  return {
    ...page,
    items: [role, ...page.items],
    total: typeof page.total === "number" ? page.total + 1 : page.total,
  };
}
