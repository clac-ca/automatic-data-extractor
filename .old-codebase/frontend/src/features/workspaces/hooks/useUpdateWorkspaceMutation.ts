import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRevalidator } from "react-router";

import { workspacesKeys, updateWorkspace, type WorkspaceUpdatePayload } from "../api";
import type { WorkspaceProfile } from "@shared/types/workspaces";

export function useUpdateWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  const revalidator = useRevalidator();

  return useMutation({
    mutationFn: (payload: WorkspaceUpdatePayload) => updateWorkspace(workspaceId, payload),
    onSuccess: (workspace) => {
      queryClient.setQueryData<WorkspaceProfile[]>(workspacesKeys.list(), (current = []) =>
        current.map((entry) => (entry.id === workspace.id ? workspace : entry)),
      );
      revalidator.revalidate();
    },
  });
}
