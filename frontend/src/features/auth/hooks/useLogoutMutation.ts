import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteSession } from "../api/client";
import { sessionKeys } from "../api/keys";

export function useLogoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteSession(),
    onSettled() {
      queryClient.removeQueries({ queryKey: sessionKeys.all, exact: false });
    },
  });
}
