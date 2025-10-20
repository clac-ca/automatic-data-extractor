import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import { createSession, sessionKeys } from "../api";
import type { LoginPayload, SessionEnvelope, SessionResponse } from "@schema/auth";

interface UseLoginMutationOptions {
  readonly onSuccess?: (session: SessionEnvelope) => void;
}

export function useLoginMutation(options: UseLoginMutationOptions = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  return useMutation<SessionEnvelope, Error, LoginPayload>({
    mutationFn: (payload: LoginPayload) => createSession(payload),
    onSuccess(session) {
      queryClient.setQueryData<SessionResponse>(sessionKeys.detail(), {
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
