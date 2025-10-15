import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace } from "../api";
import { workspaceKeys } from "./useWorkspacesQuery";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createWorkspace,
    onSuccess() {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}

