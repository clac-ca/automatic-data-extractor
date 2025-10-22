import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { completeSetup, type SetupPayload } from "../api";
import type { SessionEnvelope } from "@shared/auth/api";
import { useSessionQuery } from "../../auth/hooks/useSessionQuery";
import { sessionKeys } from "../../auth/api";
import { chooseDestination } from "../../auth/utils/authNavigation";

export function useCompleteSetupMutation() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSessionQuery({ enabled: false });

  return useMutation<SessionEnvelope, Error, SetupPayload>({
    mutationFn: (payload: SetupPayload) => completeSetup(payload),
    onSuccess(envelope) {
      queryClient.setQueryData(sessionKeys.detail(), envelope);
      const next = chooseDestination(envelope.return_to, null);
      navigate(next, { replace: true });
    },
    onSettled() {
      if (session) {
        queryClient.invalidateQueries({ queryKey: sessionKeys.detail() });
      }
    },
  });
}
