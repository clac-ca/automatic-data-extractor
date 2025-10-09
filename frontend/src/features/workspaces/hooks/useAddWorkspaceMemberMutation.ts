import { useMutation, useQueryClient } from "@tanstack/react-query";

import { addWorkspaceMember } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type {
  WorkspaceMember,
  WorkspaceMemberCreatePayload,
} from "../../../shared/api/types";

export function useAddWorkspaceMemberMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceMember, unknown, WorkspaceMemberCreatePayload>({
    mutationFn: (payload) => addWorkspaceMember(workspaceId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: workspaceKeys.members(workspaceId) });
    },
  });
}
