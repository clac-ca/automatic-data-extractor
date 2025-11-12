import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRevalidator } from "react-router";

import {
  workspacesKeys,
  updateWorkspace,
  type WorkspaceListPage,
  type WorkspaceProfile,
  type WorkspaceUpdatePayload,
  WORKSPACE_LIST_DEFAULT_PARAMS,
} from "@app/routes/workspaces/workspaces-api";

export function useUpdateWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const revalidator = useRevalidator();

  return useMutation<WorkspaceProfile, Error, WorkspaceUpdatePayload>({
    mutationFn: (payload: WorkspaceUpdatePayload) => updateWorkspace(workspaceId, payload),
    onSuccess: (workspace) => {
      queryClient.setQueryData<WorkspaceListPage>(workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS), (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: current.items.map((entry) => (entry.id === workspace.id ? workspace : entry)),
        };
      });
      revalidator.revalidate();
    },
  });
}
