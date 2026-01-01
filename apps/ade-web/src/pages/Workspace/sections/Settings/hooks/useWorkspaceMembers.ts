import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { MAX_PAGE_SIZE, useFlattenedPages } from "@api/pagination";

import { addWorkspaceMember, listWorkspaceMembers, removeWorkspaceMember, updateWorkspaceMemberRoles } from "@api/workspaces/api";
import { workspacesKeys } from "@hooks/workspaces";
import type { WorkspaceMember, WorkspaceMemberCreatePayload, WorkspaceMemberPage } from "@schema/workspaces";
import type { User } from "@schema";

const MEMBERS_PAGE_SIZE = MAX_PAGE_SIZE;

const memberListParams = {
  page: 1,
  pageSize: MEMBERS_PAGE_SIZE,
} as const;

export function useWorkspaceMembersQuery(workspaceId: string) {
  const query = useInfiniteQuery<WorkspaceMemberPage>({
    queryKey: workspacesKeys.members(workspaceId, memberListParams),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      listWorkspaceMembers(workspaceId, {
        page: typeof pageParam === "number" ? pageParam : 1,
        pageSize: MEMBERS_PAGE_SIZE,
        signal,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pageCount ? lastPage.page + 1 : undefined,
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const pages = query.data?.pages ?? [];
  const members = useFlattenedPages(pages, (member) => member.user_id);
  const total = pages[0]?.total ?? pages[pages.length - 1]?.total ?? undefined;

  return {
    ...query,
    members,
    total,
    pageSize: MEMBERS_PAGE_SIZE,
  };
}

interface AddMemberInput {
  readonly user: User;
  readonly roleIds: readonly string[];
}

export function useAddWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, memberListParams);

  return useMutation<WorkspaceMember, Error, AddMemberInput>({
    mutationFn: async ({ user, roleIds }: AddMemberInput) => {
      const payload: WorkspaceMemberCreatePayload = {
        user_id: user.id,
        role_ids: Array.from(roleIds),
      };
      return addWorkspaceMember(workspaceId, payload);
    },
    onSuccess: () => {
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
  const queryKey = workspacesKeys.members(workspaceId, memberListParams);

  return useMutation<WorkspaceMember, Error, UpdateMemberRolesInput>({
    mutationFn: ({ userId, roleIds }: UpdateMemberRolesInput) =>
      updateWorkspaceMemberRoles(workspaceId, userId, { role_ids: Array.from(roleIds) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

export function useRemoveWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, memberListParams);

  return useMutation<void, Error, string>({
    mutationFn: (userId: string) => removeWorkspaceMember(workspaceId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
