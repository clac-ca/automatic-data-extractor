import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  workspacesKeys,
  addWorkspaceMember,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspaceMemberRoles,
  type WorkspaceMember,
  type WorkspaceMemberPage,
  type WorkspaceMemberCreatePayload,
} from "@features/Workspace/api/workspaces-api";
import type { User } from "@schema";

const MEMBERS_PAGE_SIZE = 200;

export function useWorkspaceMembersQuery(workspaceId: string) {
  const memberListParams = { page: 1, pageSize: MEMBERS_PAGE_SIZE, includeTotal: true };
  return useQuery<WorkspaceMemberPage>({
    queryKey: workspacesKeys.members(workspaceId, memberListParams),
    queryFn: ({ signal }) =>
      listWorkspaceMembers(workspaceId, { signal, pageSize: MEMBERS_PAGE_SIZE, includeTotal: true }),
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

interface AddMemberInput {
  readonly user: User;
  readonly roleIds: readonly string[];
}

export function useAddWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, {
    page: 1,
    pageSize: MEMBERS_PAGE_SIZE,
    includeTotal: true,
  });

  return useMutation<
    WorkspaceMember,
    Error,
    AddMemberInput,
    { previous?: WorkspaceMemberPage; optimisticId: string }
  >({
    mutationFn: async ({ user, roleIds }: AddMemberInput) => {
      const payload: WorkspaceMemberCreatePayload = {
        user_id: user.id,
        role_ids: Array.from(roleIds),
      };
      return addWorkspaceMember(workspaceId, payload);
    },
    onMutate: async ({ user, roleIds }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMemberPage>(queryKey);
      const optimisticMember: WorkspaceMember = {
        user_id: user.id,
        role_ids: Array.from(roleIds),
        role_slugs: [],
        created_at: new Date().toISOString(),
        user,
      };
      queryClient.setQueryData<WorkspaceMemberPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: [optimisticMember, ...current.items],
          total: typeof current.total === "number" ? current.total + 1 : current.total,
        };
      });
      return { previous, optimisticId: optimisticMember.user_id };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (member, _variables, context) => {
      queryClient.setQueryData<WorkspaceMemberPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        if (!context) {
          return {
            ...current,
            items: [member, ...current.items],
            total: typeof current.total === "number" ? current.total + 1 : current.total,
          };
        }
        return {
          ...current,
          items: current.items.map((entry) =>
            entry.user_id === context.optimisticId ? { ...member, user: entry.user ?? member.user } : entry,
          ),
        };
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

interface UpdateMemberRolesInput {
  readonly userId: string;
  readonly roleIds: readonly string[];
}

export function useUpdateWorkspaceMemberRolesMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, {
    page: 1,
    pageSize: MEMBERS_PAGE_SIZE,
    includeTotal: true,
  });

  return useMutation<WorkspaceMember, Error, UpdateMemberRolesInput, { previous?: WorkspaceMemberPage }>({
    mutationFn: ({ userId, roleIds }: UpdateMemberRolesInput) =>
      updateWorkspaceMemberRoles(workspaceId, userId, { role_ids: Array.from(roleIds) }),
    onMutate: async ({ userId, roleIds }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMemberPage>(queryKey);
      queryClient.setQueryData<WorkspaceMemberPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((member) =>
            member.user_id === userId ? { ...member, role_ids: Array.from(roleIds) } : member,
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
    onSuccess: (member) => {
      queryClient.setQueryData<WorkspaceMemberPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((entry) =>
            entry.user_id === member.user_id ? { ...member, user: entry.user ?? member.user } : entry,
          ),
        };
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useRemoveWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, {
    page: 1,
    pageSize: MEMBERS_PAGE_SIZE,
    includeTotal: true,
  });

  return useMutation<void, Error, string, { previous?: WorkspaceMemberPage }>({
    mutationFn: (userId: string) => removeWorkspaceMember(workspaceId, userId),
    onMutate: async (userId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<WorkspaceMemberPage>(queryKey);
      queryClient.setQueryData<WorkspaceMemberPage>(queryKey, (current) => {
        if (!current) {
          return current;
        }
        const nextItems = current.items.filter((member) => member.user_id !== userId);
        return {
          ...current,
          items: nextItems,
          total: typeof current.total === "number" ? Math.max(current.total - 1, 0) : current.total,
        };
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
