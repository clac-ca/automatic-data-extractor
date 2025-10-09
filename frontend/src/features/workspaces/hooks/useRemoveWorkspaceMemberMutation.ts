import { useMutation, useQueryClient } from "@tanstack/react-query";

import { removeWorkspaceMember } from "../api";
import { workspaceKeys } from "./workspaceKeys";

export function useRemoveWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, unknown, string>({
    mutationFn: (membershipId) => removeWorkspaceMember(workspaceId, membershipId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: workspaceKeys.members(workspaceId) });
    },
  });
}
