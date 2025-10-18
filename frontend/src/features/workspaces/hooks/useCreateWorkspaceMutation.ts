import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createWorkspace } from "../api";
import { workspacesKeys } from "../api/keys";

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createWorkspace,
    onSuccess() {
      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
    },
  });
}
