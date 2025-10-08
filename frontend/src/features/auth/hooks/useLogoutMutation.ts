import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { deleteSession } from "../api";
import { sessionKeys } from "./sessionKeys";

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: deleteSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionKeys.all });
      queryClient.removeQueries({ queryKey: sessionKeys.all });
      navigate("/login", { replace: true });
    },
  });
}
