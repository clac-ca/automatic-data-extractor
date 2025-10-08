import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type { CreateWorkspacePayload, WorkspaceProfile } from "../../../shared/api/types";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceProfile, Error, CreateWorkspacePayload>({
    mutationFn: (payload) => createWorkspace(payload),
    onSuccess: async (workspace) => {
      queryClient.setQueryData<WorkspaceProfile[]>(workspaceKeys.lists(), (previous = []) => {
        const alreadyExists = previous.some((entry) => entry.id === workspace.id);
        if (alreadyExists) {
          return previous;
        }

        return [...previous, workspace];
      });

      await queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() });
    },
  });
}
