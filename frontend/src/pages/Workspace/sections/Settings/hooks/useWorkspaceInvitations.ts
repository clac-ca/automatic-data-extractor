import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelInvitation,
  listInvitations,
  resendInvitation,
  type Invitation,
  type InvitationList,
} from "@/api/invitations/api";

const invitationsKey = (workspaceId: string) => ["workspaces", workspaceId, "invitations"] as const;

export function useWorkspaceInvitationsQuery(workspaceId: string) {
  return useQuery<InvitationList>({
    queryKey: invitationsKey(workspaceId),
    queryFn: ({ signal }) =>
      listInvitations({
        workspaceId,
        signal,
      }),
    enabled: workspaceId.length > 0,
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  });
}

export function useResendWorkspaceInvitationMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<Invitation, Error, string>({
    mutationFn: (invitationId) => resendInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: invitationsKey(workspaceId) });
    },
  });
}

export function useCancelWorkspaceInvitationMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<Invitation, Error, string>({
    mutationFn: (invitationId) => cancelInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: invitationsKey(workspaceId) });
    },
  });
}
