import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  workspacesKeys,
  addWorkspaceMember,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspaceMemberRoles,
} from "@app/routes/workspaces/workspaces-api";
import type { components } from "@openapi";

export function useWorkspaceMembersQuery(workspaceId: string) {
  return useQuery<WorkspaceMember[]>({
    queryKey: workspacesKeys.members(workspaceId),
    queryFn: ({ signal }) => listWorkspaceMembers(workspaceId, signal),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous ?? [],
  });
}

interface AddMemberInput {
  readonly user: UserProfile;
  readonly roleIds: readonly string[];
}

export function useAddWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId);

  return useMutation<WorkspaceMember, Error, AddMemberInput, { previous?: WorkspaceMember[]; optimisticId: string }>({
    mutationFn: async ({ user, roleIds }: AddMemberInput) => {
      return addWorkspaceMember(workspaceId, { user_id: user.user_id, role_ids: roleIds });
    },
    onMutate: async ({ user, roleIds }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMember[]>(queryKey);
      const optimisticMember: WorkspaceMember = {
        workspace_membership_id: `optimistic-${Date.now()}`,
        workspace_id: workspaceId,
        roles: Array.from(roleIds),
        permissions: [],
        is_default: false,
        user,
      };
      queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
        const list = current ?? [];
        return [optimisticMember, ...list];
      });
      return { previous, optimisticId: optimisticMember.workspace_membership_id };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (member, _variables, context) => {
      if (!context) {
        queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
          const list = current ?? [];
          return [member, ...list];
        });
        return;
      }
      queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((entry) =>
          entry.workspace_membership_id === context.optimisticId ? member : entry,
        );
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

interface UpdateMemberRolesInput {
  readonly membershipId: string;
  readonly roleIds: readonly string[];
}

export function useUpdateWorkspaceMemberRolesMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId);

  return useMutation<WorkspaceMember, Error, UpdateMemberRolesInput, { previous?: WorkspaceMember[] }>({
    mutationFn: ({ membershipId, roleIds }: UpdateMemberRolesInput) =>
      updateWorkspaceMemberRoles(workspaceId, membershipId, roleIds),
    onMutate: async ({ membershipId, roleIds }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMember[]>(queryKey);
      queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((member) =>
          member.workspace_membership_id === membershipId
            ? { ...member, roles: Array.from(roleIds) }
            : member,
        );
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (member) => {
      queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.map((entry) =>
          entry.workspace_membership_id === member.workspace_membership_id ? member : entry,
        );
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useRemoveWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId);

  return useMutation<void, Error, string, { previous?: WorkspaceMember[] }>({
    mutationFn: (membershipId: string) => removeWorkspaceMember(workspaceId, membershipId),
    onMutate: async (membershipId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMember[]>(queryKey);
      queryClient.setQueryData<WorkspaceMember[]>(queryKey, (current) => {
        const list = current ?? [];
        return list.filter((member) => member.workspace_membership_id !== membershipId);
      });
      return { previous };
    },
    onError: (_error, _membershipId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

type WorkspaceMember = components["schemas"]["WorkspaceMember"];
type UserProfile = components["schemas"]["UserProfile"];
