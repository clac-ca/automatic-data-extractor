import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace } from "@api/workspaces/api";
import { workspacesKeys } from "./keys";
import type { WorkspaceCreatePayload, WorkspaceListPage, WorkspaceProfile } from "@schema/workspaces";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceProfile, Error, WorkspaceCreatePayload>({
    mutationFn: createWorkspace,
    onSuccess(workspace) {
      queryClient.setQueryData(workspacesKeys.detail(workspace.id), workspace);

      queryClient.getQueriesData<WorkspaceListPage>({ queryKey: workspacesKeys.all() }).forEach(([key, page]) => {
        if (!Array.isArray(key) || key[0] !== "workspaces" || key[1] !== "list" || !page) {
          return;
        }

        const existingIndex = page.items.findIndex((item: WorkspaceProfile) => item.id === workspace.id);
        const mergedItems =
          existingIndex >= 0
            ? page.items.map((item: WorkspaceProfile) => (item.id === workspace.id ? workspace : item))
            : [...page.items, workspace];

        const sortedItems = [...mergedItems].sort((a, b) => a.name.localeCompare(b.name));
        const total = typeof page.total === "number" && existingIndex === -1 ? page.total + 1 : page.total;

        queryClient.setQueryData(key, { ...page, items: sortedItems, total });
      });

      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
    },
  });
}
