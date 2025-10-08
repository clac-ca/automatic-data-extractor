import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { completeSetup, fetchSetupStatus, fetchSession } from "../../auth/api";
import { setupKeys } from "./useSetupStatusQuery";
import { sessionKeys } from "../../auth/hooks/sessionKeys";
import type { CompleteSetupPayload } from "../../../shared/api/types";

export function useCompleteSetupMutation() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (payload: CompleteSetupPayload) => completeSetup(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: setupKeys.all });
      await queryClient.invalidateQueries({ queryKey: sessionKeys.all });
      const session = await fetchSession();
      queryClient.setQueryData(sessionKeys.detail(), session);
      navigate("/workspaces", { replace: true });
    },
    onError: async () => {
      await queryClient.invalidateQueries({ queryKey: setupKeys.all });
      await fetchSetupStatus();
    },
  });
}
