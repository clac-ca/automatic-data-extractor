import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createWorkspace,
  workspacesKeys,
  type WorkspaceCreatePayload,
  type WorkspaceProfile,
} from "@screens/Workspace/api/workspaces-api";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceProfile, Error, WorkspaceCreatePayload>({
    mutationFn: createWorkspace,
    onSuccess() {
      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
    },
  });
}
