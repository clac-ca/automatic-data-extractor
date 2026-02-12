import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { MAX_PAGE_SIZE, useFlattenedPages } from "@/api/pagination";
import { createInvitation } from "@/api/invitations/api";
import {
  addWorkspacePrincipalRoles,
  listWorkspacePrincipals,
  removeWorkspacePrincipal,
  updateWorkspacePrincipalRoles,
} from "@/api/workspaces/api";
import { workspacesKeys } from "@/hooks/workspaces";
import type {
  WorkspacePrincipal,
  WorkspacePrincipalPage,
  WorkspacePrincipalType,
} from "@/types/workspaces";
import type { User } from "@/types";

const PRINCIPALS_PAGE_SIZE = MAX_PAGE_SIZE;

const principalListParams = {
  limit: PRINCIPALS_PAGE_SIZE,
} as const;

export function useWorkspacePrincipalsQuery(workspaceId: string) {
  const query = useInfiniteQuery<WorkspacePrincipalPage>({
    queryKey: workspacesKeys.principals(workspaceId, principalListParams),
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) =>
      listWorkspacePrincipals(workspaceId, {
        limit: PRINCIPALS_PAGE_SIZE,
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
  const principals = useFlattenedPages(
    pages,
    (principal) => `${principal.principal_type}:${principal.principal_id}`,
  );
  const users = principals.filter((principal) => principal.principal_type === "user");
  const groups = principals.filter((principal) => principal.principal_type === "group");
  const total = pages[0]?.meta.totalCount ?? principals.length;

  return {
    ...query,
    principals,
    users,
    groups,
    total,
    pageSize: PRINCIPALS_PAGE_SIZE,
  };
}

interface AddPrincipalInput {
  readonly principalType: WorkspacePrincipalType;
  readonly principalId?: string;
  readonly user?: User;
  readonly invitedEmail?: string;
  readonly displayName?: string;
  readonly roleIds: readonly string[];
}

export function useAddWorkspacePrincipalMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.principals(workspaceId, principalListParams);

  return useMutation<WorkspacePrincipal, Error, AddPrincipalInput>({
    mutationFn: async ({
      principalType,
      principalId,
      user,
      invitedEmail,
      displayName,
      roleIds,
    }: AddPrincipalInput) => {
      if (roleIds.length === 0) {
        throw new Error("Select at least one role.");
      }

      if (principalType === "user" && invitedEmail?.trim()) {
        const invitation = await createInvitation({
          invitedUserEmail: invitedEmail.trim().toLowerCase(),
          displayName: displayName?.trim() || null,
          workspaceContext: {
            workspaceId,
            roleAssignments: roleIds.map((roleId) => ({ roleId })),
          },
        });

        return {
          principal_type: "user",
          principal_id: invitation.invited_user_id ?? `invited:${invitation.email_normalized}`,
          principal_display_name: displayName?.trim() || invitation.email_normalized,
          principal_email: invitation.email_normalized,
          principal_slug: null,
          role_ids: [...roleIds],
          role_slugs: [],
          created_at: invitation.created_at,
        };
      }

      const resolvedPrincipalId =
        principalId ?? (principalType === "user" ? user?.id : undefined);
      if (!resolvedPrincipalId) {
        throw new Error("Select an existing principal or provide an invitation email.");
      }

      return addWorkspacePrincipalRoles(workspaceId, {
        principal_type: principalType,
        principal_id: resolvedPrincipalId,
        role_ids: Array.from(roleIds),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId, "invitations"] });
    },
  });
}

interface UpdatePrincipalRolesInput {
  readonly principalType: WorkspacePrincipalType;
  readonly principalId: string;
  readonly roleIds: readonly string[];
}

export function useUpdateWorkspacePrincipalRolesMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.principals(workspaceId, principalListParams);

  return useMutation<WorkspacePrincipal | null, Error, UpdatePrincipalRolesInput>({
    mutationFn: ({ principalType, principalId, roleIds }: UpdatePrincipalRolesInput) =>
      updateWorkspacePrincipalRoles(workspaceId, principalType, principalId, {
        role_ids: Array.from(roleIds),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}

interface RemovePrincipalInput {
  readonly principalType: WorkspacePrincipalType;
  readonly principalId: string;
}

export function useRemoveWorkspacePrincipalMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const queryKey = workspacesKeys.principals(workspaceId, principalListParams);

  return useMutation<void, Error, RemovePrincipalInput>({
    mutationFn: ({ principalType, principalId }) =>
      removeWorkspacePrincipal(workspaceId, principalType, principalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
