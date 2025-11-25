import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  workspacesKeys,
  updateWorkspace,
  type WorkspaceListPage,
  type WorkspaceProfile,
  type WorkspaceUpdatePayload,
  WORKSPACE_LIST_DEFAULT_PARAMS,
} from "@screens/Workspace/api/workspaces-api";

export function useUpdateWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();

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
      queryClient.invalidateQueries({ queryKey: workspacesKeys.detail(workspaceId), exact: false });
    },
  });
}
