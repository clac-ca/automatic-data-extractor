import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateWorkspace } from "@api/workspaces/api";
import { workspacesKeys } from "./keys";
import type { WorkspaceListPage, WorkspaceProfile, WorkspaceUpdatePayload } from "@schema/workspaces";

export function useUpdateWorkspaceMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceProfile, Error, WorkspaceUpdatePayload>({
    mutationFn: (payload) => updateWorkspace(workspaceId, payload),
    onSuccess: (workspace) => {
      queryClient.setQueryData(workspacesKeys.detail(workspace.id), workspace);

      queryClient.getQueriesData<WorkspaceListPage>({ queryKey: workspacesKeys.all() }).forEach(([key, page]) => {
        if (!Array.isArray(key) || key[0] !== "workspaces" || key[1] !== "list" || !page) {
          return;
        }

        const items = page.items.map((entry: WorkspaceProfile) => (entry.id === workspace.id ? workspace : entry));
        const sortedItems = [...items].sort((a, b) => a.name.localeCompare(b.name));

        queryClient.setQueryData(key, { ...page, items: sortedItems });
      });
    },
  });
}
