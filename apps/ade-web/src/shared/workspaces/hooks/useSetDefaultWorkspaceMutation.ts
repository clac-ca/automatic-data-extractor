import { useMutation, useQueryClient } from "@tanstack/react-query";

import { setDefaultWorkspace } from "../api";
import { workspacesKeys } from "../keys";
import type { WorkspaceListPage, WorkspaceProfile } from "../types";

function applyDefaultWorkspaceSelection(cached: unknown, workspaceId: string): unknown {
  if (!cached || typeof cached !== "object") {
    return cached;
  }

  if ("items" in cached) {
    const list = cached as WorkspaceListPage;
    if (!Array.isArray(list.items)) {
      return cached;
    }
    const items = list.items.map((workspace) => ({
      ...workspace,
      is_default: workspace.id === workspaceId,
    }));
    return { ...list, items };
  }

  if ("id" in cached && "is_default" in cached) {
    const workspace = cached as WorkspaceProfile;
    return { ...workspace, is_default: workspace.id === workspaceId };
  }

  return cached;
}

export function useSetDefaultWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (workspaceId: string) => setDefaultWorkspace(workspaceId),
    onSuccess: (_data, workspaceId) => {
      queryClient.setQueriesData({ queryKey: workspacesKeys.all() }, (cached) =>
        applyDefaultWorkspaceSelection(cached, workspaceId),
      );
    },
  });
}

