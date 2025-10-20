import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  workspacesKeys,
  createWorkspaceRole,
  deleteWorkspaceRole,
  listPermissions,
  listWorkspaceRoles,
  updateWorkspaceRole,
} from "@app/routes/workspaces/workspaces-api";
import type { RoleCreatePayload, RoleDefinition, RoleUpdatePayload, PermissionDefinition } from "@schema/roles";

export function useWorkspaceRolesQuery(workspaceId: string) {
  return useQuery<RoleDefinition[]>({
    queryKey: workspacesKeys.roles(workspaceId),
    queryFn: ({ signal }) => listWorkspaceRoles(workspaceId, signal),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function usePermissionsQuery() {
  return useQuery<PermissionDefinition[]>({
    queryKey: workspacesKeys.permissions(),
    queryFn: ({ signal }) => listPermissions(signal),
    staleTime: 60_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useCreateWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId);

  return useMutation<RoleDefinition, Error, RoleCreatePayload, { previous?: RoleDefinition[]; optimisticId: string }>({
    mutationFn: (payload: RoleCreatePayload) => createWorkspaceRole(workspaceId, payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleDefinition[]>(queryKey);
      const optimisticRole: RoleDefinition = {
        role_id: `optimistic-${Date.now()}`,
        slug: payload.slug ?? payload.name.toLowerCase().replace(/\s+/g, "-"),
        name: payload.name,
        description: payload.description ?? null,
        scope_type: "workspace",
        scope_id: workspaceId,
        permissions: Array.from(payload.permissions ?? []),
        built_in: false,
        editable: true,
      };
      queryClient.setQueryData<RoleDefinition[]>(queryKey, (current) => {
        const list = current ?? [];
        return [optimisticRole, ...list];
      });
      return { previous, optimisticId: optimisticRole.role_id };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (role, _variables, context) => {
      if (!context) {
        queryClient.setQueryData<RoleDefinition[]>(queryKey, (current = []) => [role, ...current]);
        return;
      }
      queryClient.setQueryData<RoleDefinition[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((entry) => (entry.role_id === context.optimisticId ? role : entry));
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
  const queryKey = workspacesKeys.roles(workspaceId);

  return useMutation<RoleDefinition, Error, UpdateRoleInput, { previous?: RoleDefinition[] }>({
    mutationFn: ({ roleId, payload }: UpdateRoleInput) => updateWorkspaceRole(workspaceId, roleId, payload),
    onMutate: async ({ roleId, payload }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleDefinition[]>(queryKey);
      queryClient.setQueryData<RoleDefinition[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((role) =>
          role.role_id === roleId
            ? {
                ...role,
                name: payload.name,
                description: payload.description ?? null,
                permissions: Array.from(payload.permissions ?? []),
              }
            : role,
        );
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (role) => {
      queryClient.setQueryData<RoleDefinition[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((entry) => (entry.role_id === role.role_id ? role : entry));
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useDeleteWorkspaceRoleMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.roles(workspaceId);

  return useMutation<void, Error, string, { previous?: RoleDefinition[] }>({
    mutationFn: (roleId: string) => deleteWorkspaceRole(workspaceId, roleId),
    onMutate: async (roleId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RoleDefinition[]>(queryKey);
      queryClient.setQueryData<RoleDefinition[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.filter((role) => role.role_id !== roleId);
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
