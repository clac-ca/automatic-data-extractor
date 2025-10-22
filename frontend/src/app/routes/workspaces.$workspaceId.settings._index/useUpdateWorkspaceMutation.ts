import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRevalidator } from "react-router";

import {
  workspacesKeys,
  updateWorkspace,
  type WorkspaceProfile,
  type WorkspaceUpdatePayload,
} from "@app/routes/workspaces/workspaces-api";

export function useUpdateWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const revalidator = useRevalidator();

  return useMutation<WorkspaceProfile, Error, WorkspaceUpdatePayload>({
    mutationFn: (payload: WorkspaceUpdatePayload) => updateWorkspace(workspaceId, payload),
    onSuccess: (workspace) => {
      queryClient.setQueryData<WorkspaceProfile[]>(workspacesKeys.list(), (current) => {
        const list = current ?? [];
        return list.map((entry) => (entry.id === workspace.id ? workspace : entry));
      });
      revalidator.revalidate();
    },
  });
}
