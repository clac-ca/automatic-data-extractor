import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace, workspacesKeys } from "../api";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createWorkspace,
    onSuccess() {
      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
    },
  });
}
