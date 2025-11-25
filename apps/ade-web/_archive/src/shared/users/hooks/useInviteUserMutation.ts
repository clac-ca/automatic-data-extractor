import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inviteUser } from "../api";

interface InviteUserInput {
  readonly email: string;
  readonly displayName?: string;
}

export function useInviteUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, displayName }: InviteUserInput) =>
      inviteUser({
        email,
        display_name: displayName?.trim() ? displayName.trim() : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users", "all"] });
    },
  });
}
