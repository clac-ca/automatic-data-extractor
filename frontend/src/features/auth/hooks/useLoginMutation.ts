import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { createSession, fetchSession } from "../api";
import { sessionKeys } from "./sessionKeys";
import type { LoginPayload } from "../../../shared/api/types";
import { resolveSessionDestination } from "../utils/resolveSessionDestination";

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (payload: LoginPayload) => createSession(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionKeys.all });
      const resolvedSession = await fetchSession();
      queryClient.setQueryData(sessionKeys.detail(), resolvedSession);

      navigate(resolveSessionDestination(resolvedSession), { replace: true });
    },
  });
}
