import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import { createSession } from "../api/client";
import { sessionKeys } from "../api/keys";
import type { LoginPayload, SessionEnvelope } from "../../../shared/types/auth";

interface UseLoginMutationOptions {
  readonly onSuccess?: (session: SessionEnvelope) => void;
}

export function useLoginMutation(options: UseLoginMutationOptions = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: LoginPayload) => createSession(payload),
    onSuccess(session) {
      queryClient.setQueryData(sessionKeys.detail(), {
        session,
        providers: [],
        force_sso: false,
      });
      const searchParams = new URLSearchParams(location.search);
      const next = session.return_to ?? searchParams.get("next") ?? "/";
      options.onSuccess?.(session);
      navigate(next, { replace: true });
    },
  });
}
