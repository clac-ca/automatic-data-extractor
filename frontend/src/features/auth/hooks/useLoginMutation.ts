import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { createSession, fetchSession } from "../api";
import { sessionKeys } from "./sessionKeys";
import type { LoginPayload } from "../../../shared/api/types";

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (payload: LoginPayload) => createSession(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionKeys.all });
      const resolvedSession = await fetchSession();
      queryClient.setQueryData(sessionKeys.detail(), resolvedSession);

      const preferredWorkspace = resolvedSession?.user.preferred_workspace_id ?? undefined;
      if (preferredWorkspace) {
        navigate(`/workspaces/${preferredWorkspace}`, { replace: true });
      } else {
        navigate("/workspaces", { replace: true });
      }
    },
  });
}
