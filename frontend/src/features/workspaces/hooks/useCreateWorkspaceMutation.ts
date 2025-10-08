import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type { CreateWorkspacePayload, WorkspaceListResponse, WorkspaceSummary } from "../../../shared/api/types";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceSummary, Error, CreateWorkspacePayload>({
    mutationFn: (payload) => createWorkspace(payload),
    onSuccess: async (workspace) => {
      queryClient.setQueryData(workspaceKeys.lists(), (previous?: WorkspaceListResponse) => {
        if (!previous) {
          return { workspaces: [workspace] } satisfies WorkspaceListResponse;
        }

        const alreadyExists = previous.workspaces.some((entry) => entry.id === workspace.id);
        if (alreadyExists) {
          return previous;
        }

        return { workspaces: [...previous.workspaces, workspace] } satisfies WorkspaceListResponse;
      });

      await queryClient.invalidateQueries({ queryKey: workspaceKeys.lists() });
    },
  });
}
