import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteSession, sessionKeys } from "../api";

export function useLogoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteSession(),
    onSettled() {
      queryClient.removeQueries({ queryKey: sessionKeys.all, exact: false });
    },
  });
}
