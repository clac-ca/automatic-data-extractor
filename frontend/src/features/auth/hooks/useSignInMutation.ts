import { useMutation } from "@tanstack/react-query";

import { signIn, type SignInCredentials } from "@api/auth";
import type { Session } from "@app/providers/SessionProvider";
import { useApiClient } from "@hooks/useApiClient";

interface SignInResult {
  readonly session: Session;
}

export function useSignInMutation() {
  const client = useApiClient();

  return useMutation<SignInResult, Error, SignInCredentials>({
    mutationFn: async (credentials) => ({
      session: await signIn(client, credentials)
    })
  });
}
