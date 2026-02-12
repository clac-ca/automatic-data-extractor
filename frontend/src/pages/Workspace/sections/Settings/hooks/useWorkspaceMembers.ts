import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { MAX_PAGE_SIZE, useFlattenedPages } from "@/api/pagination";
import { createInvitation } from "@/api/invitations/api";

import { addWorkspaceMember, listWorkspaceMembers, removeWorkspaceMember, updateWorkspaceMemberRoles } from "@/api/workspaces/api";
import { workspacesKeys } from "@/hooks/workspaces";
import type { WorkspaceMember, WorkspaceMemberCreatePayload, WorkspaceMemberPage } from "@/types/workspaces";
import type { User } from "@/types";

const MEMBERS_PAGE_SIZE = MAX_PAGE_SIZE;

const memberListParams = {
  limit: MEMBERS_PAGE_SIZE,
} as const;

export function useWorkspaceMembersQuery(workspaceId: string) {
  const query = useInfiniteQuery<WorkspaceMemberPage>({
    queryKey: workspacesKeys.members(workspaceId, memberListParams),
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) =>
      listWorkspaceMembers(workspaceId, {
        limit: MEMBERS_PAGE_SIZE,
        cursor: typeof pageParam === "string" ? pageParam : null,
        includeTotal: true,
        signal,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.meta.hasMore ? lastPage.meta.nextCursor ?? undefined : undefined,
    enabled: workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const pages = query.data?.pages ?? [];
  const members = useFlattenedPages(pages, (member) => member.user_id);
  const total = pages[0]?.meta.totalCount ?? undefined;

  return {
    ...query,
    members,
    total,
    pageSize: MEMBERS_PAGE_SIZE,
  };
}

interface AddMemberInput {
  readonly user?: User;
  readonly invitedEmail?: string;
  readonly displayName?: string;
  readonly roleIds: readonly string[];
}

export function useAddWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.members(workspaceId, memberListParams);

  return useMutation<WorkspaceMember, Error, AddMemberInput>({
    mutationFn: async ({ user, invitedEmail, displayName, roleIds }: AddMemberInput) => {
      if (!user && !invitedEmail) {
        throw new Error("Select an existing user or provide an invitation email.");
      }
      if (roleIds.length === 0) {
        throw new Error("Select at least one role.");
      }
      if (invitedEmail) {
        const invitation = await createInvitation({
          invitedUserEmail: invitedEmail,
          displayName: displayName ?? null,
          workspaceContext: {
            workspaceId,
            roleAssignments: roleIds.map((roleId) => ({ roleId })),
          },
        });
        return {
          user_id: invitation.invited_user_id ?? "",
          role_ids: [...roleIds],
          role_slugs: [],
          created_at: invitation.created_at,
          user: invitation.invited_user_id
            ? ({
                id: invitation.invited_user_id,
                email: invitation.email_normalized,
                display_name: displayName ?? null,
              } as WorkspaceMember["user"])
            : undefined,
        };
      }
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
