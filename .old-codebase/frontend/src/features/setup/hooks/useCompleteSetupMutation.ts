
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { completeSetup } from "../api";
import { useSessionQuery } from "../../auth/hooks/useSessionQuery";
import { sessionKeys } from "../../auth/api";
import type { SetupPayload } from "@shared/types/auth";

export function useCompleteSetupMutation() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSessionQuery({ enabled: false });

  return useMutation({
    mutationFn: (payload: SetupPayload) => completeSetup(payload),
    onSuccess(envelope) {
      queryClient.setQueryData(sessionKeys.detail(), {
        session: envelope,
        providers: [],
        force_sso: false,
      });
      const next = envelope.return_to ?? "/";
      navigate(next, { replace: true });
    },
    onSettled() {
      if (session) {
        queryClient.invalidateQueries({ queryKey: sessionKeys.detail() });
      }
    },
  });
}
