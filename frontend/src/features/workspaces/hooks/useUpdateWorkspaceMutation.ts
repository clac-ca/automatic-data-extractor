import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRevalidator } from "react-router-dom";

import { workspacesKeys } from "../api/keys";
import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { updateWorkspace, type WorkspaceUpdatePayload } from "../api/client";

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
